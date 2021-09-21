import numpy as np
from models import model
import torch
from robustness.datasets import CIFAR
import dill

from utils import dev

import tqdm


def get_dist_dec(orig, label, dirs, model, n_samples=1000):
    shape = orig.shape
    n_steps = 20
    n_dirs = len(dirs)
    dirs = dirs.reshape((n_dirs, -1))

    upper = np.ones((n_samples, 1)) * 10
    lower = np.zeros((n_samples, 1))

    scales = np.ones((n_samples, 1)) * 10

    coeffs = abs(np.random.normal(size=[n_samples, n_dirs]))
    sample_dirs = (coeffs @ dirs)
    sample_dirs = sample_dirs / np.linalg.norm(sample_dirs, axis=-1, keepdims=True)

    dists = np.full(n_samples, np.nan)

    for i in range(n_steps):
        input_dirs = scales * sample_dirs
        input_ = (input_dirs + orig.flatten()[None])
        input = torch.split(torch.tensor(input_.reshape((-1,) + shape), device=dev()), 100)

        preds = np.empty((0, 10))
        for batch in input:
            preds = np.concatenate((preds, model(batch).detach().cpu().numpy()), axis=0)
        pred_classes = np.argmax(preds, axis=-1)

        is_adv = np.invert(pred_classes == label)
        dists[is_adv] = scales[is_adv, 0]

        upper[is_adv] = scales[is_adv]
        lower[~is_adv] = scales[~is_adv]
        scales[is_adv] = upper[is_adv] / 2
        scales[~is_adv] = (upper[~is_adv] + lower[~is_adv]) / 2

    in_bounds = np.logical_or(input_.max(-1) <= 1, input_.min(-1) >= 0)
    dists[~in_bounds] = np.nan
    return dists


# Load models

ds = CIFAR('./data/cifar-10-batches-py')
classifier_model = ds.get_model('resnet50', False)
model_natural = model.cifar_pretrained(classifier_model, ds)

resume_path = './models/cifar_nat.pt'
checkpoint = torch.load(resume_path, pickle_module=dill, map_location=torch.device(dev()))

state_dict_path = 'model'
if not ('model' in checkpoint):
    state_dict_path = 'state_dict'
sd = checkpoint[state_dict_path]
sd = {k[len('module.'):]: v for k, v in sd.items()}
model_natural.load_state_dict(sd)
model_natural.to(dev())
model_natural.double()
model_natural.eval()

classifier_model = ds.get_model('resnet50', False)
model_robust = model.cifar_pretrained(classifier_model, ds)

resume_path = './models/cifar_l2_0_5.pt'
checkpoint = torch.load(resume_path, pickle_module=dill, map_location=torch.device(dev()))

state_dict_path = 'model'
if not ('model' in checkpoint):
    state_dict_path = 'state_dict'
sd = checkpoint[state_dict_path]
sd = {k[len('module.'):]: v for k, v in sd.items()}
model_robust.load_state_dict(sd)
model_robust.to(dev())
model_robust.double()
model_robust.eval()

# load data
data_nat = np.load('./data/cifar_natural.npy', allow_pickle=True).item()
advs = data_nat['advs']
pert_lengths = data_nat['pert_lengths']
classes = data_nat['adv_class']
dirs = data_nat['dirs']
images = data_nat['images']
labels = data_nat['labels']
pert_lengths = data_nat['pert_lengths']

data_madry = np.load('./data/cifar_robust.npy', allow_pickle=True).item()
advs_madry = data_madry['advs']
pert_lengths_madry = data_madry['pert_lengths']
classes_madry = data_madry['adv_class']
dirs_madry = data_madry['dirs']

n_samples = 5000
n_dims = 50
n_images = 5

# img_indices = np.random.choice(np.arange(100), size=n_images, replace=False)
img_indices = np.array([18, 36, 67, 88, 92])

#natural
images_ = images[img_indices]
labels_ = labels[img_indices]
dirs_ = dirs[img_indices]
dists_natural = np.zeros((len(images_),n_dims,n_samples))

for i, img in enumerate(tqdm.tqdm(images_)):
    for n in np.arange(1,n_dims+1):
        dists_natural[i, n-1] = get_dist_dec(img, labels_[i], dirs_[i,:n], model_natural, n_samples=n_samples)

#robust
dirs_ = dirs_madry[img_indices]
dists_robust = np.zeros((len(images_), n_dims, n_samples))

for i, img in enumerate(tqdm.tqdm(images_)):
    for n in np.arange(1, n_dims + 1):
        dists_robust[i, n - 1] = get_dist_dec(img, labels_[i], dirs_[i, :n], model_robust, n_samples=n_samples)

data = {
    'dists_natural': dists_natural,
    'dists_robust': dists_robust
}

save_path = './data/dists_to_bnd_many_samples.npy'
np.save(save_path, data)