from matplotlib import pyplot as plt
import numpy as np
from utils import dev
import torch
from mpl_toolkits.mplot3d import art3d
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap


def plot_advs(advs, shape, orig=None, classes=None, orig_class=None, n=10, vmin=0, vmax=1, ax=None):
    if orig is None:
        j = 0
    else:
        j = 1
    with_classes = True

    if classes is None:
        with_classes = False

    dirs = advs - np.reshape(orig, (1,-1))

    max_val = np.maximum(abs(np.min(dirs)), abs(np.max(dirs)))
    min_val = - max_val

    if shape[0]==3:
        dirs = np.reshape(dirs, ((-1,) + shape)).transpose((0,2,3,1))
        advs = np.reshape(advs, ((-1,) + shape)).transpose((0,2,3,1))
    else:
        dirs = np.reshape(dirs, [-1,shape[1],shape[2]])
        advs = np.reshape(advs, [-1,shape[1],shape[2]])
    
    if ax is None:
        ax_arg = None
        fig, ax = plt.subplots(2, n + j, squeeze=False)
    else:
        ax_arg = ax

    if not (orig is None):
        if shape[0]==3:
            orig = np.reshape(orig, shape)
        else:
            orig = np.reshape(orig, shape[1:])
        ax[0, 0].set_title('original')
        ax[0, 0].imshow(orig, cmap='gray', vmin=vmin, vmax=vmax)
        ax[0, 0].set_xticks([])
        ax[0, 0].set_yticks([])
        ax[0, 0].set_xlabel(str(orig_class), fontdict={'fontsize': 15})

        ax[1, 0].axis('off')

    for i, (a, d) in enumerate(zip(advs[:n], dirs[:n])):
        ax[0, i + j].set_title('Adversarial ' + str(i + 1))
        if with_classes:
            #ax[0, i + j].set_xlabel('\u279E ' + str(int(classes[i])), fontdict={'fontsize': 15})
            ax[0, i + j].set_xlabel(r'$\rightarrow$ ' + str(int(classes[i])))
        if a.ndim == 1:
            a_side = int(np.sqrt(a.size))
            a = a.reshape((a_side, a_side))
        im_adv = ax[0, i + j].imshow(a, cmap='gray', vmin=vmin, vmax=vmax)
        ax[0, i + j].set_xticks([])
        ax[0, i + j].set_yticks([])
        ax[1, i + j].set_title('Perturbation ' + str(i + 1))

        im_pert = ax[1, i + j].imshow(d, vmin=min_val, vmax=max_val)
        ax[1, i + j].set_xticks([])
        ax[1, i + j].set_yticks([])

    #ax[1, n+j-1].set_xlabel('magnification factor ' + str(np.round(1/max_val, 2)), horizontalalignment='right', x=1.0)
    if ax_arg is None:
        fig.colorbar(im_adv, ax=ax[0, :].ravel().tolist(), shrink=0.7)
        fig.colorbar(im_pert, ax=ax[1, :].ravel().tolist(), shrink=0.7)
    else:
        ax[0, :].colorbar(im_adv, shrink=0.7)
        ax[1, :].colorbar(im_pert, shrink=0.7)

    if ax_arg is None:
        return fig, ax


def plot_mean_advs(advs, images, classes, labels, pert_lengths, n=10, vmin=0, vmax=1):

    mean_pert_length = np.mean(pert_lengths, axis=0)
    dist_to_mean = np.sum(np.abs(pert_lengths - mean_pert_length), axis=-1)
    min_idx = np.argmin(dist_to_mean)
    return plot_advs(advs[min_idx], images[min_idx], classes[min_idx], labels[min_idx], n=n, vmin=vmin, vmax=vmax)


def plot_pert_lengths(pert_lengths, n=10, labels=None, ord=2, showmeans=False):
    n = np.minimum(n, pert_lengths[0].shape[1])
    pert_lengths = [p[:,:n] for p in pert_lengths]
    colors = ['blue', 'orange', 'green']
    l = []

    fig, ax = plt.subplots()
    for i, pl in enumerate(pert_lengths):
        boxprops = dict(color=colors[i], linewidth=1.5, alpha=0.7)
        whiskerprops = dict(color=colors[i], alpha=0.7)
        capprops = dict(color=colors[i], alpha=0.7)
        medianprops = dict(linestyle='--', linewidth=1, color=colors[i])
        meanprops = dict(linestyle='-', linewidth=1, color=colors[i])


        if not labels is None:
            l.append(mpatches.Patch(color=colors[i], label=labels[i]))

        pl[pl==0] = np.nan
        mask = ~np.isnan(pl)
        filtered_data = [d[m] for d, m in zip(pl.T, mask.T)]
        ax.boxplot(filtered_data, whis=[10,90], showfliers=False, meanline=showmeans, showmeans=showmeans, boxprops=boxprops,
                    whiskerprops=whiskerprops, capprops=capprops, meanprops=meanprops,  medianprops=medianprops)
    plt.title('Perturbation length of first ' + str(n) + ' adversarial directions')
    plt.xlabel('d')
    if ord == np.inf:
        plt.ylabel('adversarial vector length ($\ell_\infty-norm$)')
    else:
        plt.ylabel('adversarial vector length ($\ell_%d-norm$)' % (ord))
    if not (labels is None):
        plt.legend(handles=l)
    return fig, ax


def plot_pert_lengths_single(adv_class, pert_lengths):
    plt.figure(figsize=(7, 5))
    classes = np.unique(adv_class)
    for c in classes:
        plt.scatter(np.argwhere(np.array(adv_class) == c)+1,
                    pert_lengths[np.array(adv_class) == c],
                    label='target class ' + str(c))
    plt.title('Perturbation lengths of first ' + str(len(pert_lengths)) + 'adversarial directions')
    plt.xlabel('n')
    plt.ylabel('adversarial vector length ($l2-norm$)')
    plt.legend()
    plt.show()



def plot_cw_surface(orig, adv1, adv2, model):
    orig = np.reshape(orig, (784))
    len1 = np.linalg.norm(adv1-orig)
    len2 = np.linalg.norm(adv2-orig)
    dir1 = (adv1 - orig) / len1
    dir2 = (adv2 - orig) / len2

    n_grid = 100
    len_grid = 2.5
    offset = 0.1
    x = np.linspace(-offset, len_grid, n_grid)
    y = np.linspace(-offset, len_grid, n_grid)
    X, Y = np.meshgrid(x, y)
    advs = orig + (dir1*np.reshape(X,(-1,1)) + dir2*np.reshape(Y,(-1,1)))
    advs = np.array(np.reshape(advs, (-1,1,28,28)).astype('float64'), dtype='float32')
    input = torch.split(torch.tensor(advs), 20)

    preds = np.empty((0,10))
    for batch in input:
        preds = np.concatenate((preds, model(batch).detach().cpu().numpy()),axis=0)
    preds = np.exp(preds) / np.sum(np.exp(preds), axis=-1)[:, np.newaxis]
    orig_pred = model(torch.tensor(np.reshape(orig, (1, 1, 28, 28)))).detach().cpu().numpy()
    orig_pred = np.exp(orig_pred) / np.sum(np.exp(orig_pred), axis=-1)[:, np.newaxis]

    label = np.argmax(orig_pred)
    conf = preds[:,label].reshape((n_grid,n_grid))
    classes = np.argmax(preds,axis=-1).reshape((n_grid,n_grid))

    fig = plt.figure()
    ax = fig.gca(projection='3d')
    plot_colors = np.empty(X.shape, dtype=object)
    colors = ['orange', 'green', 'brown', 'grey', 'pink', 'blue','cyan', 'olive', 'red', 'purple']
    labels = []
    for i, c in enumerate(np.unique(classes)):
        labels.append(mpatches.Patch(color=colors[c], label='Class ' + str(c)))
        plot_colors[classes == c] = colors[c]

    # Plot the surface.
    ax.plot_surface(X, Y, conf, linewidth=0, antialiased=False, facecolors=plot_colors)
    p = mpatches.Circle((offset, offset), .1, ec='k', fc='k')
    ax.add_patch(p)
    art3d.pathpatch_2d_to_3d(p, z=orig_pred[0, label], zdir='z')


    ax.set_xlabel('dir 1 ($\ell_2-length$)')
    ax.set_ylabel('dir 2 ($\ell_2-length$)')
    ax.set_zlabel('confidence in original class')
    ax.set_zlim((0,1))

    # Add legend with proxy artists
    plt.legend(handles=labels, title='class with largest confidence')
    plt.show()


def plot_dec_space(orig, adv1, adv2, model, offset=0.1, len_grid_scale=2, n_grid=100,
                   show_legend=True, show_advs=True, align_ticks=False,
                   overlay_inbounds=False, origin_centered=False, colors=None, ax=None):
    if ax is None:
        fig, ax = plt.subplots()
    if orig.ndim == 3:
        input_shape = orig.shape
    else: # batch singleton dimension included
        input_shape = orig.shape[1:]
    orig = orig.flatten()
    pert1 = adv1 - orig
    pert2 = adv2 - orig
    len1 = np.linalg.norm(pert1)
    len2 = np.linalg.norm(pert2)
    dir1 = pert1 / len1
    dir2 = pert2 / len2

    len_grid = len_grid_scale * np.maximum(len1,len2)
    if origin_centered:
        offset=len_grid

    x = np.linspace(-offset, len_grid, n_grid)
    y = np.linspace(-offset, len_grid, n_grid)
    X, Y = np.meshgrid(x, y)
    advs = orig + (dir1[None, :] * np.reshape(X, (-1, 1)) + dir2[None, :] * np.reshape(Y, (-1, 1)))
    advs = np.array(np.reshape(advs, ((-1,) + input_shape)).astype('float64'))
    input = torch.split(torch.tensor(advs, device=dev()), 20)

    preds = np.empty((0, 10))
    for batch in input:
        preds = np.concatenate((preds, model(batch).detach().cpu().numpy()), axis=0)

    classes = np.argmax(preds, axis=-1).reshape((n_grid, n_grid))
    if colors is None:
        colors = ['orange', 'green', 'brown', 'grey', 'blue', 'pink','cyan', 'olive', 'red', 'purple']
    labels = []
    colorList = []
    for i, c in enumerate(np.unique(classes)):
        labels.append(mpatches.Patch(color=colors[c], label=str(c)))
        colorList.append(colors[c])
    # Plot the surface.
    new_cmap = ListedColormap(colors)

    ax.imshow(classes, cmap=new_cmap, origin='lower', interpolation=None, vmin=0, vmax=9)
    if overlay_inbounds:
        new_cmap2 = ListedColormap(['none', 'k'])
        out_of_bounds = np.logical_or(advs.max(axis=(1,2,3))>1, advs.min(axis=(1,2,3))<0).reshape((n_grid, n_grid))
        ax.imshow(out_of_bounds, cmap=new_cmap2, origin='lower', alpha=.5, vmin=0, vmax=1)

    ax.axvline(offset*n_grid/(offset+len_grid), c='k', ls='--', alpha=0.5)
    ax.axhline(offset*n_grid/(offset+len_grid), c='k', ls='--', alpha=0.5)

    ax.plot(offset*n_grid/(offset+len_grid), offset*n_grid/(offset+len_grid),
             markeredgecolor='black', markerfacecolor='black', marker='o')

    if show_advs:
        adv_locs = [# [[adv1_y, adv1_x], [adv2_y, adv2_x]]
            [
                offset * n_grid / (offset + len_grid),
                (offset + len1) * n_grid / (offset + len_grid)
            ],[
                (offset + len2) * n_grid / (offset + len_grid),
                offset * n_grid / (offset + len_grid)
            ]
        ]
        ax.plot(adv_locs[0][1], adv_locs[0][0],
                 markeredgecolor='black', markerfacecolor='red', marker='o')
        ax.plot(adv_locs[1][1], adv_locs[1][0],
                 markeredgecolor='black', markerfacecolor='red', marker='o')

    #ax.set_xlabel('dir 1 ($\ell_2$-length)', fontdict={'fontsize': 15})
    #ax.set_ylabel('dir 2 ($\ell_2$-length)', fontdict={'fontsize': 15})

    if align_ticks:
        x_ticks = np.arange(len1, np.maximum(len_grid,offset), len1)
        x_ticks = np.r_[-x_ticks[::-1], 0, x_ticks]
        x_ticks = x_ticks[x_ticks>=-offset]
        x_ticks = x_ticks[x_ticks<=len_grid]
        x_tick_locs = (x_ticks+offset)/(len_grid+offset)*n_grid
        ax.set_xticks(x_tick_locs)
        ax.set_xticklabels([np.round(x, 2).astype(str) for x in x_ticks])
        
        y_ticks = np.arange(len2, np.maximum(len_grid,offset), len2)
        y_ticks = np.r_[-y_ticks[::-1], 0, y_ticks]
        y_ticks = y_ticks[y_ticks>=-offset]
        y_ticks = y_ticks[y_ticks<=len_grid]
        y_tick_locs = (y_ticks+offset)/(len_grid+offset)*n_grid
        ax.set_yticks(y_tick_locs)
        ax.set_yticklabels([np.round(x, 2).astype(str) for x in y_ticks])
    else:
        data_ticks = np.linspace(offset*n_grid/(offset+len_grid), (offset+np.floor(len_grid))*n_grid/(offset+len_grid), 5)
        plot_ticks = [np.round(x, 2).astype(str) for x in np.linspace(0, np.floor(len_grid), 5)]
        ax.set_xticks(data_ticks, minor=False)
        ax.set_xticklabels(plot_ticks)
        ax.set_yticks(data_ticks, minor=False)
        ax.set_yticklabels(plot_ticks)

    if show_legend: # Add legend with proxy artists
        if origin_centered:
            ax.legend(handles=labels, title='predicted class', loc='lower left')
        else:
            ax.legend(handles=labels, title='predicted class')
    
    if ax is None:
        return fig, ax, advs, labels
    else:
        return advs, labels



def plot_var_hist(classes, labels, title=None, with_colors=True):
    bar_width = 0.4
    colors = ['blue', 'orange', 'green', 'purple', 'red', 'brown', 'grey', 'pink',
              'cyan', 'olive']
    data = np.zeros((10,10))
    for l in range(10):
        var = np.mean(np.array([(len(np.unique(x[~np.isnan(x)]))-1)/(len(x[~np.isnan(x)])-1) for x in classes[labels == l]]))
        u, c = np.unique(classes[labels == l], return_counts=True)
        c = c[~np.isnan(u)]
        u = u[~np.isnan(u)]
        data[u.astype(int), l] = c / np.sum(c) * var

    y_off = np.zeros(10)

    fig, ax = plt.subplots()
    for idx in range(10):
        if with_colors:
            ax.bar(range(10), data[idx], bar_width, bottom=y_off,  color=colors[idx])
            plt.legend(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'], title='adversarial label',
                       bbox_to_anchor=(1.05, 1), loc='upper left')
        else:
            ax.bar(range(10), data[idx], bar_width, bottom=y_off, color='k')

        y_off += data[idx]
    plt.xlabel('original class label')
    plt.ylabel('mean number of adversarial classes')
    plt.xticks(range(10))
    if not title is None:
        plt.title(title)
    plt.ylim(0,1)
    plt.tight_layout()

    return fig, ax
