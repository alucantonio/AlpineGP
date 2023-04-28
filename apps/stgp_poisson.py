from dctkit.dec import cochain as C
from dctkit.mesh.simplex import SimplicialComplex
from dctkit.math.opt import optctrl as oc
# import networkx as nx
import matplotlib.pyplot as plt
from matplotlib import tri
from deap import gp, base
import dctkit
from alpine.models.poisson import pset
from alpine.data import poisson_dataset as d
from alpine.gp import gpsymbreg as gps

import numpy as np
import warnings
import jax.numpy as jnp
import math
import mpire
import time
import sys
import yaml
import os
from os.path import join
from typing import Tuple, Callable
import numpy.typing as npt

apps_path = os.path.dirname(os.path.realpath(__file__))

# choose precision and whether to use GPU or CPU
dctkit.config(dctkit.FloatDtype.float64, dctkit.IntDtype.int64,
              dctkit.Backend.jax, dctkit.Platform.cpu)


# suppress warnings
warnings.filterwarnings('ignore')

# list of types
types = [C.CochainP0, C.CochainP1, C.CochainP2,
         C.CochainD0, C.CochainD1, C.CochainD2, float]

# extract list of names of primitives
primitives_strings = gps.get_primitives_strings(pset, types)


class Objectives():
    def __init__(self, S: SimplicialComplex, bnodes: npt.NDArray, gamma: float) -> None:
        self.S = S
        self.bnodes = bnodes
        self.gamma = gamma

    def set_energy_func(self, func: Callable, individual: gp.PrimitiveTree) -> None:
        """Set the energy function to be used for the computation of the objective
        function."""
        self.energy_func = func
        self.individual = individual

    def total_energy(self, x, vec_y, vec_bvalues):
        penalty = 0.5*self.gamma*jnp.sum((x[self.bnodes] - vec_bvalues)**2)
        c = C.CochainP0(self.S, x)
        fk = C.CochainP0(self.S, vec_y)
        total_energy = self.energy_func(c, fk) + penalty
        return total_energy


def eval_MSE(individual: gp.PrimitiveTree, X: np.array, y: np.array,
             bvalues: dict, S: SimplicialComplex, bnodes: np.array,
             gamma: float, u_0: np.array, toolbox: base.Toolbox,
             return_best_sol=False) -> float:

    num_nodes = X.shape[1]

    # transform the individual expression into a callable function
    energy_func = toolbox.compile(expr=individual)

    obj = Objectives(S=S, bnodes=bnodes, gamma=gamma)
    obj.set_energy_func(energy_func, individual)

    prb = oc.OptimizationProblem(
        dim=num_nodes, state_dim=num_nodes, objfun=obj.total_energy)

    total_err = 0.

    best_sols = []

    # TODO: parallelize
    for i, vec_y in enumerate(y):
        # extract current bvalues
        vec_bvalues = bvalues[i, :]

        # set current bvalues and vec_y for the Poisson problem
        args = {'vec_y': vec_y, 'vec_bvalues': vec_bvalues}
        prb.set_obj_args(args)

        # minimize the objective
        x = prb.run(x0=u_0.coeffs)

        if return_best_sol:
            best_sols.append(x)

        current_err = np.linalg.norm(x-X[i, :])**2

        if current_err > 100 or math.isnan(current_err):
            current_err = 100

        total_err += current_err

    if return_best_sol:
        return best_sols

    total_err *= 1/X.shape[0]

    return total_err


def eval_fitness(individual: gp.PrimitiveTree, X: np.array, y: np.array, bvalues: dict,
                 S: SimplicialComplex, bnodes: np.array, gamma: float, u_0: np.array,
                 penalty: dict, toolbox: base.Toolbox) -> Tuple[float, ]:

    objval = 0.

    total_err = eval_MSE(individual, X, y, bvalues, S, bnodes, gamma, u_0, toolbox)

    if penalty["method"] == "primitive":
        # penalty terms on primitives
        indstr = str(individual)
        objval = total_err + penalty["reg_param"] * \
            max([indstr.count(string) for string in primitives_strings])
    elif penalty["method"] == "length":
        # penalty terms on length
        objval = total_err + penalty["reg_param"]*len(individual)
    else:
        # no penalty
        objval = total_err
    return objval,


# Plot best solution
def plot_sol(ind: gp.PrimitiveTree, X: np.array, y: np.array, bvalues: dict,
             S: SimplicialComplex, bnodes: np.array, gamma: float, u_0: np.array,
             triang: tri.Triangulation,  toolbox: base.Toolbox):
    u = eval_MSE(ind, X=X, y=y, bvalues=bvalues, S=S,
                 bnodes=bnodes, gamma=gamma, u_0=u_0, toolbox=toolbox,
                 return_best_sol=True)
    plt.figure(10, figsize=(8, 4))
    fig = plt.gcf()
    _, axes = plt.subplots(2, 3, num=10)
    for i in range(0, 3):
        axes[0, i].tricontourf(triang, u[i], cmap='RdBu', levels=20)
        pltobj = axes[1, i].tricontourf(triang, X[i], cmap='RdBu', levels=20)
        axes[0, i].set_box_aspect(1)
        axes[1, i].set_box_aspect(1)
    plt.colorbar(pltobj, ax=axes)
    fig.canvas.draw()
    fig.canvas.flush_events()
    plt.pause(0.1)


def stgp_poisson(config_file, output_path=None):
    # generate mesh and dataset
    S, bnodes, triang = d.generate_complex(0.08)
    num_nodes = S.num_nodes
    X_train, X_val, X_test, y_train, y_val, y_test = d.load_dataset()

    # extract boundary values
    bvalues_train = X_train[:, bnodes]
    bvalues_val = X_val[:, bnodes]
    bvalues_test = X_test[:, bnodes]

    # penalty parameter for the Dirichlet bcs
    gamma = 1000.

    # initial guess for the solution
    u_0_vec = 0.01*np.random.rand(num_nodes)
    u_0 = C.CochainP0(S, u_0_vec)

    # set parameters from config file
    GPproblem_settings, GPproblem_run, GPproblem_extra = gps.load_config_data(
        config_file_data=config_file, pset=pset)
    toolbox = GPproblem_settings['toolbox']
    penalty = GPproblem_extra['penalty']
    n_jobs = GPproblem_extra['n_jobs']

    # set arguments for evaluate functions
    if GPproblem_run['early_stopping']['enabled']:
        args_train = {'X': X_train, 'y': y_train, 'bvalues': bvalues_train,
                      'penalty': penalty, 'S': S, 'bnodes': bnodes,
                      'gamma': gamma, 'u_0': u_0, 'toolbox': toolbox}
        args_val_fit = {'X': X_val, 'y': y_val, 'bvalues': bvalues_val,
                        'penalty': penalty, 'S': S,
                        'bnodes': bnodes, 'gamma': gamma, 'u_0': u_0, 'toolbox': toolbox}
        args_val_MSE = {'X': X_val, 'y': y_val, 'bvalues': bvalues_val, 'S': S,
                        'bnodes': bnodes, 'gamma': gamma, 'u_0': u_0, 'toolbox': toolbox}

        # register functions for fitness/MSE evaluation on different datasets
        toolbox.register("evaluate_val_fit", eval_fitness, **args_val_fit)
        toolbox.register("evaluate_val_MSE", eval_MSE, **args_val_MSE)
    else:
        X_tr = np.vstack((X_train, X_val))
        y_tr = np.vstack((y_train, y_val))
        bvalues_tr = np.vstack((bvalues_train, bvalues_val))
        args_train = {'X': X_tr, 'y': y_tr, 'bvalues': bvalues_tr,
                      'penalty': penalty, 'S': S, 'bnodes': bnodes,
                      'gamma': gamma, 'u_0': u_0, 'toolbox': toolbox}

    # register functions for fitness evaluation on training dataset
    toolbox.register("evaluate_train", eval_fitness, **args_train)

    if GPproblem_run['plot_best']:
        toolbox.register("plot_best_func", plot_sol, **args_val_MSE,
                         toolbox=toolbox, triang=triang)

    # create symbolic regression problem instance
    GPproblem = gps.GPSymbRegProblem(pset=pset, **GPproblem_settings)

    # opt_string = "Sub(MulF(Inn1(dP0(u), dP0(u)), 1/2), Inn0(u,fk))"
    # opt_individ = creator.Individual.from_string(opt_string, pset)
    # seed = [opt_individ]

    pool = mpire.WorkerPool(n_jobs=n_jobs)
    GPproblem.toolbox.register("map", pool.map)

    start = time.perf_counter()

    GPproblem.run(plot_history=False, print_log=True, seed=None, **GPproblem_run)

    best = GPproblem.best
    print(f"The best individual is {str(best)}", flush=True)

    print(f"The best fitness on the training set is {GPproblem.train_fit_history[-1]}")
    if GPproblem_run['early_stopping']['enabled']:
        print(f"The best fitness on the validation set is {GPproblem.min_valerr}")

    print("> MODEL TRAINING/SELECTION COMPLETED", flush=True)

    score_test = eval_MSE(best, X_test, y_test, bvalues_test, S=S,
                          bnodes=bnodes, gamma=gamma, u_0=u_0, toolbox=toolbox)
    print(f"The best MSE on the test set is {score_test}")

    print(f"Elapsed time: {round(time.perf_counter() - start, 2)}")

    pool.terminate()

    # plot the tree of the best individual
    # nodes, edges, labels = gp.graph(best)
    # graph = nx.Graph()
    # graph.add_nodes_from(nodes)
    # graph.add_edges_from(edges)
    # pos = nx.nx_agraph.graphviz_layout(graph, prog="dot")
    # plt.figure(figsize=(7, 7))
    # nx.draw_networkx_nodes(graph, pos, node_size=900, node_color="w")
    # nx.draw_networkx_edges(graph, pos)
    # nx.draw_networkx_labels(graph, pos, labels)
    # plt.axis("off")
    # plt.show()

    # save string of best individual in .txt file
    file = open(join(output_path, "best_ind.txt"), "w")
    file.write(str(best))
    file.close()

    # save data for plots to disk
    np.save(join(output_path, "train_fit_history.npy"),
            GPproblem.train_fit_history)
    if GPproblem_run['early_stopping']['enabled']:
        np.save(join(output_path, "val_fit_history.npy"), GPproblem.val_fit_history)

    best_sols = eval_MSE(best, X=X_test, y=y_test,
                         bvalues=bvalues_test, S=S,
                         bnodes=bnodes, gamma=gamma,
                         u_0=u_0, toolbox=toolbox, return_best_sol=True)

    for i, sol in enumerate(best_sols):
        np.save(join(output_path, "best_sol_test_" + str(i) + ".npy"), sol)
        np.save(join(output_path, "true_sol_test_" + str(i) + ".npy"), X_test[i])


if __name__ == '__main__':
    n_args = len(sys.argv)
    assert n_args > 1, "Parameters filename needed."
    param_file = sys.argv[1]
    print("Parameters file: ", param_file)
    with open(param_file) as file:
        config_file = yaml.safe_load(file)
        print(yaml.dump(config_file))

    # path for output data speficified
    if n_args >= 3:
        output_path = sys.argv[2]
    else:
        output_path = "."

    stgp_poisson(config_file, output_path)
