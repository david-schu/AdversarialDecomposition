from typing import Union, Tuple, Any, Optional
from functools import partial
import numpy as np
import eagerpy as ep
import foolbox as fb
from foolbox import attacks as fa
from foolbox.models import Model
from foolbox.distances import LpDistance
from foolbox.criteria import Misclassification, TargetedMisclassification
from foolbox.attacks.base import MinimizationAttack, T, get_criterion, raise_if_kwargs

# import matplotlib
# import matplotlib.pyplot as plt
# matplotlib.use('TkAgg')

class OrthogonalAttack(MinimizationAttack):
    def __init__(self, input_attack, params, adv_dirs=[], random_start=False):
        super(OrthogonalAttack,self).__init__()
        self.input_attack = input_attack(**params)
        self.distance = LpDistance(2)
        self.dirs = adv_dirs
        self.random_start = random_start

    def run(self, model, inputs, criterion, **kwargs):
        return self.input_attack.run(model, inputs, criterion, dirs=self.dirs, random_start=self.random_start, **kwargs)

    def distance(self):
        ...


class CarliniWagner(fa.L2CarliniWagnerAttack):
    def run(
        self,
        model: Model,
        inputs: T,
        criterion: Union[Misclassification, TargetedMisclassification, T],
        *,
        early_stop: Optional[float] = None,
        random_start: Optional[float] = None,
        dirs: Optional[Any] = [],
        ** kwargs: Any,
    ) -> T:
        raise_if_kwargs(kwargs)
        x, restore_type = ep.astensor_(inputs)
        criterion_ = get_criterion(criterion)
        dirs = ep.astensor(dirs)  ##################
        del inputs, criterion, kwargs

        N = len(x)

        if isinstance(criterion_, Misclassification):
            targeted = False
            classes = criterion_.labels
            change_classes_logits = self.confidence
        elif isinstance(criterion_, TargetedMisclassification):
            targeted = True
            classes = criterion_.target_classes
            change_classes_logits = -self.confidence
        else:
            raise ValueError("unsupported 500criterion")

        def is_adversarial(perturbed: ep.Tensor, logits: ep.Tensor) -> ep.Tensor:
            if change_classes_logits != 0:
                logits += ep.onehot_like(logits, classes, value=change_classes_logits)
            return criterion_(perturbed, logits)

        if classes.shape != (N,):
            name = "target_classes" if targeted else "labels"
            raise ValueError(
                f"expected {name} to have shape ({N},), got {classes.shape}"
            )

        bounds = model.bounds
        to_attack_space = partial(fa.carlini_wagner._to_attack_space, bounds=bounds)
        to_model_space = partial(fa.carlini_wagner._to_model_space, bounds=bounds)

        x_attack = to_attack_space(x)
        reconstructed_x = to_model_space(x_attack)
        rows = range(N)
        losses = np.zeros((self.binary_search_steps, self.steps))

        def loss_fun(
                delta: ep.Tensor, consts: ep.Tensor
        ) -> Tuple[ep.Tensor, Tuple[ep.Tensor, ep.Tensor]]:
            assert delta.shape == x_attack.shape
            assert consts.shape == (N,)

            ######## by David ############
            adv = to_model_space(x_attack + delta)
            orth_loss = False
            if len(dirs) > 0:
                orth_loss=True
                # _x = reconstructed_x.flatten(-3, -1)
                # _d = dirs.flatten(-2, -1)
                # _s = (adv - reconstructed_x).float32().flatten(-3, -1).expand_dims(1)
                #
                # gram_schmidt = ((_d * _s).sum(-1).expand_dims(-1)*_d).sum(1)
                # adv_orth = adv - (gram_schmidt).reshape(adv.shape)
                #
                # if adv_orth.max() > 1 or adv_orth.min() < 0:
                #     orth_loss = True
                # else:
                #     adv = adv - (gram_schmidt).reshape(adv.shape)

            logits = model(adv)
            # ###############################

            if targeted:
                c_minimize = fa.carlini_wagner.best_other_classes(logits, classes)
                c_maximize = classes  # target_classes
            else:
                c_minimize = classes  # labels
                c_maximize = fa.carlini_wagner.best_other_classes(logits, classes)

            is_adv_loss = logits[rows, c_minimize] - logits[rows, c_maximize]
            assert is_adv_loss.shape == (N,)

            is_adv_loss = is_adv_loss + self.confidence
            is_adv_loss = ep.maximum(0, is_adv_loss)
            is_adv_loss = is_adv_loss * consts
            squared_norms = (adv - reconstructed_x).flatten(1,-1).square().sum(axis=-1)

            if orth_loss:
                is_orth = dirs.flatten(-2,-1) * (adv-x).flatten(-2, -1).expand_dims(1)
                is_orth = is_orth.sum(axis=-1).square().sum(axis=-1) * consts*10e4
                loss = is_adv_loss.sum() + squared_norms.sum() + is_orth.sum()
                losses[binary_search_step, step] = is_orth.sum().raw
            else:
                loss = is_adv_loss.sum() + squared_norms.sum()

            return loss, (adv, logits)

        loss_aux_and_grad = ep.value_and_grad_fn(x, loss_fun, has_aux=True)

        consts = self.initial_const * np.ones((N,))
        lower_bounds = np.zeros((N,))
        upper_bounds = np.inf * np.ones((N,))

        best_advs = ep.zeros_like(x)
        best_advs_norms = ep.full(x, (N,), ep.inf)
        best_binary_step = 0
        # the binary search searches for the smallest consts that produce adversarials
        for binary_search_step in range(self.binary_search_steps):
            if (
                    binary_search_step == self.binary_search_steps - 1
                    and self.binary_search_steps >= 10
            ):
                # in the last binary search step, repeat the search once
                consts = np.minimum(upper_bounds, 1e10)

            # create a new optimizer find the delta that minimizes the loss
            delta = ep.zeros_like(x_attack)
            if random_start:
                delta = delta.uniform(shape=delta.shape, low=-0.1, high=0.1)

            optimizer = fa.carlini_wagner.AdamOptimizer(delta)

            # tracks whether adv with the current consts was found
            found_advs = np.full((N,), fill_value=False)
            loss_at_previous_check = np.inf

            consts_ = ep.from_numpy(x, consts.astype(np.float32))
            for step in range(self.steps):

                loss, (perturbed, logits), gradient = loss_aux_and_grad(delta, consts_)
                learning_rate = 0.005 / 5*np.ceil((3*step+1)/self.steps)
                delta += optimizer(gradient, learning_rate)

                if self.abort_early and step % (np.ceil(self.steps / 10)) == 0:
                    # after each tenth of the overall steps, check progress
                    if not (loss <= 0.9999 * loss_at_previous_check):
                        break  # stop Adam if there has been no progress
                    loss_at_previous_check = loss

                found_advs_iter = is_adversarial(perturbed, logits)
                found_advs = np.logical_or(found_advs, found_advs_iter.numpy())

                norms = (perturbed - x).flatten().norms.l2(axis=-1)
                closer = norms < best_advs_norms
                new_best = ep.logical_and(closer, found_advs_iter)

                new_best_ = fb.devutils.atleast_kd(new_best, best_advs.ndim)
                best_advs = ep.where(new_best_, perturbed, best_advs)
                best_advs_norms = ep.where(new_best, norms, best_advs_norms)

                if new_best:
                    best_binary_step = binary_search_step

            upper_bounds = np.where(found_advs, consts, upper_bounds)
            lower_bounds = np.where(found_advs, lower_bounds, consts)

            consts_exponential_search = consts * 10
            consts_binary_search = (lower_bounds + upper_bounds) / 2
            consts = np.where(
                np.isinf(upper_bounds), consts_exponential_search, consts_binary_search
            )

        # if len(dirs)>0:
        #     plt.figure()
        #     plt.plot(range(self.steps), losses[best_binary_step])
        #     plt.ylim(0, 10)
        #     plt.savefig('../data/losses/loss' + str(dirs.shape[1],) + '.png' )
        print('Best binary search step %d, const %.2f' % (best_binary_step, consts[0]))
        return restore_type(best_advs)
