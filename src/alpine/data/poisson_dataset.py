import numpy as np
# import multiprocessing
import gmsh
from dctkit.mesh import simplex, util
import os
from sklearn.model_selection import train_test_split, KFold


cwd = os.path.dirname(simplex.__file__)


def generate_complex(filename):
    """Generate a Simplicial complex and its boundary nodes from a msh file.

    Args:
        filename (str): name of the msh file (with .msh at the end).

    Returns:
        (SimplicialComplex): resulting simplicial complex.
        (np.array): np.array containing the positions of the boundary nodes.
    """
    full_path = os.path.join(cwd, filename)
    _, _, S_2, node_coords = util.read_mesh(full_path)

    S = simplex.SimplicialComplex(S_2, node_coords)
    S.get_circumcenters()
    S.get_primal_volumes()
    S.get_dual_volumes()
    S.get_hodge_star()

    bnodes, _ = gmsh.model.mesh.getNodesForPhysicalGroup(1, 1)
    bnodes -= 1

    return S, bnodes


def generate_dataset(S, mult, diff):
    """Generate a dataset for the Poisson problem.

    Args:
        S (SimplicialComplex): simplicial complex where the functions of the dataset
        are defined.
        mult (int): the multiplicity of every class (for now 3) of functions of the
        dataset.
        diff (int): integer (from 1 to 3) that expresses the number of classes of
        different functions in the dataset.

    Returns:
        (np.array): np.array of the dataset samples.
        (np.array): np.array of the labels.
    """
    node_coords = S.node_coord
    num_nodes = S.num_nodes
    data_X = np.empty((diff*mult, num_nodes))
    data_y = np.empty((diff*mult, num_nodes))
    for i in range(mult):
        if diff >= 1:
            # ith quadratic function
            q_i = 1/(i + 1)**2 * (node_coords[:, 0]**2 + node_coords[:, 1]**2)
            rhs_qi = (4/(i+1)**2) * np.ones(num_nodes)
            data_X[diff*i, :] = q_i
            data_y[diff*i, :] = rhs_qi

        if diff >= 2:
            # ith exponential function
            trig_i = np.cos(i*node_coords[:, 0]) + np.sin(i*node_coords[:, 1])
            rhs_trigi = -i**2 * trig_i
            data_X[diff*i+1, :] = trig_i
            data_y[diff*i+1, :] = rhs_trigi

        if diff >= 3:
            # ith power function
            p_i = node_coords[:, 0]**(i+2) + node_coords[:, 1]**(i+2)
            rhs_pi = (i+2)*(i+1)*(node_coords[:, 0]**(i) + node_coords[:, 1]**(i))
            data_X[diff*i+2, :] = p_i
            data_y[diff*i+2, :] = rhs_pi

    return data_X, data_y


def split_dataset(S, num_per_data, diff, perc, is_valid=False):
    """Split the dataset in training and test set (hold out) and initialize k-fold
    cross validation.

    Args:
        S (SimplicialComplex): a simplicial complex.
        num_per_data (int): 1/3 of the size of the dataset
        diff (int): integer (from 1 to 3) that expresses the number of classes of
        different functions in the dataset.
        perc (float): percentage of the dataset dedicated to test set
        is_valid (bool): boolean that it is True if we want to do model selection
        (validation process).

    Returns:
        (tuple): tuple of training and test samples.
        (tuple): tuple of training and test targets.
        (KFold): KFold class initialized.
    """
    data_X, data_y = generate_dataset(S, num_per_data, diff)

    if not is_valid:
        return data_X, data_y

    # split the dataset in training and test set
    X_train, X_test, y_train, y_test = train_test_split(
        data_X, data_y, test_size=perc, random_state=None)

    X = (X_train, X_test)
    y = (y_train, y_test)

    return X, y
