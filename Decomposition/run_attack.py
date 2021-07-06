import torch
from attacks import OrthogonalAttack, CarliniWagner
from utils import classification, dev
from tqdm import tqdm
import foolbox
from utils import orth_check

def run_attack(model,
              image,
              label,
              attack_params,
              random_start=True,
              input_attack=CarliniWagner,
              n_adv_dims=3,
              early_stop=3,
              epsilons=[None],
              verbose=False
    ):
    fmodel = foolbox.models.PyTorchModel(model,  # return logits in shape (bs, n_classes)
                                         bounds=(0., 1.),  # num_classes=10,
                                         device=dev())

    # initialize variables
    n_pixel = image.shape[-1] ** 2
    n_channels = image.shape[1]
    x_orig = image.reshape([n_channels, n_pixel])

    count = 0
    pert_lengths = torch.zeros(n_adv_dims, device=dev())
    adv_class = torch.zeros(n_adv_dims, device=dev(), dtype=int)
    advs = torch.zeros((n_adv_dims, n_channels, n_pixel), device=dev())
    adv_dirs = torch.zeros((n_adv_dims, n_channels, n_pixel), device=dev())
    dirs=[]

    for run in tqdm(range(n_adv_dims), leave=False):
        if verbose:
            print('Run %d' % (run + 1))

        attack = OrthogonalAttack(input_attack=input_attack,
                                  params=attack_params,
                                  adv_dirs=dirs,
                                  random_start=random_start)

        _, adv, success = attack(fmodel, image, label, epsilons=epsilons)
        adv = adv[0]
        # check if adversarials were found and stop early if not
        if success.sum() == 0 or (adv==0).all():
            print('--No attack within bounds found--')
            count += 1
            if early_stop == count:
                print('No more adversarials found ----> early stop!')
                break
            continue

        count = 0

        class_ = classification(adv, model)[0]
        a_ = adv.flatten()
        pert_length = torch.norm(a_ - x_orig)

        advs[run] = a_
        adv_dir = (a_ - x_orig) / pert_length
        adv_dirs[run] = adv_dir
        adv_class[run] = class_
        pert_lengths[run] = pert_length

        dirs = adv_dirs[:run+1].flatten(-2, -1).detach().cpu().numpy()
        # print(orth_check(dirs[0]))


    return advs, adv_dirs, adv_class, pert_lengths