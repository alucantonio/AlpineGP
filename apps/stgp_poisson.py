from dctkit.dec import cochain as C
import networkx as nx
import matplotlib.pyplot as plt
import jax.config as config
from deap import gp
import dctkit
from alpine.models.poisson import pset
from alpine.data import poisson_dataset as d
from alpine.gp import gpsymbreg as gps

import numpy as np
import warnings
import jax.numpy as jnp
from jax import jit, grad
from scipy.optimize import minimize
import operator
import math
import mpire
import time
import sys
import yaml

# choose precision and whether to use GPU or CPU
dctkit.config(dctkit.FloatDtype.float64, dctkit.IntDtype.int64,
              dctkit.Backend.jax, dctkit.Platform.cpu)


# suppress warnings
warnings.filterwarnings('ignore')

# generate mesh and dataset
S, bnodes, triang = d.generate_complex("test3.msh")
num_nodes = S.num_nodes

# set default GP parameters
NINDIVIDUALS = 10
NGEN = 20
CXPB = 0.5
MUTPB = 0.1
frac_elitist = 0.1


# number of different source term functions to use to generate the dataset
num_sources = 3
# number of cases for each source term function
num_samples_per_source = 4
# whether to use validation dataset
use_validation = True

# noise
noise = 0.*np.random.rand(num_nodes)

data_X, data_y = d.generate_dataset(S, num_samples_per_source, num_sources, noise)
X, y = d.split_dataset(data_X, data_y, 0.25, 0.25, use_validation)

if use_validation:
    X_train, X_val, X_test = X
    y_train, y_val,  y_test = y
    # extract boundary values for the test set
    bvalues_test = X_test[:, bnodes]
else:
    X_train = X
    y_train = y

# extract bvalues_train
bvalues_train = X_train[:, bnodes]
bvalues_val = X_val[:, bnodes]

gamma = 1000.

# initial guess for the solution
u_0_vec = 0.01*np.random.rand(num_nodes)
u_0 = C.CochainP0(S, u_0_vec)


class ObjFunction:
    def __init__(self) -> None:
        pass

    def set_energy_func(self, func, individual):
        """Set the energy function to be used for the computation of the objective
        function."""
        self.energy_func = func
        self.individual = individual

    def total_energy(self, vec_x, vec_y, vec_bvalues):
        penalty = 0.5*gamma*jnp.sum((vec_x[bnodes] - vec_bvalues)**2)
        c = C.CochainP0(S, vec_x)
        fk = C.CochainP0(S, vec_y)
        energy = self.energy_func(c, fk) + penalty
        return energy


def eval_MSE(individual, X, y, bvalues, return_best_sol=False):
    """Evaluate total MSE over datasets."""

    # transform the individual expression into a callable function
    energy_func = GPproblem.toolbox.compile(expr=individual)

    # create objective function and set its energy function
    obj = ObjFunction()
    obj.set_energy_func(energy_func, individual)

    # compute/compile jacobian of the objective wrt its first argument (vec_x)
    jac = jit(grad(obj.total_energy))

    total_err = 0.

    # TODO: parallelize using vmap once we can use jaxopt
    for i, vec_y in enumerate(y):
        # extract current bvalues
        vec_bvalues = bvalues[i, :]

        # minimize the objective
        x = minimize(fun=obj.total_energy, x0=u_0.coeffs,
                     args=(vec_y, vec_bvalues), method="L-BFGS-B", jac=jac).x
        if return_best_sol:
            return x

        current_err = np.linalg.norm(x-X[i, :])**2

        if current_err > 100 or math.isnan(current_err):
            current_err = 100

        total_err += current_err

    total_err *= 1/(num_sources*num_samples_per_source)

    return total_err


def eval_fitness(individual, X, y, bvalues, reg_param):
    objval = 0.

    total_err = eval_MSE(individual, X, y, bvalues)
    # length_penalty = min([np.abs(len(individual) - i) for i in range(1, 41)])

    # Penatly terms on model complexity
    indstr = str(individual)
    nMulFloat = indstr.count("MulF")
    nAdd = indstr.count("Add")
    nSub = indstr.count("Sub")
    nDiv = indstr.count("Div")
    nExpF = indstr.count("ExpF")
    nLogF = indstr.count("LogF")
    nSinF = indstr.count("SinF")
    nArcsinF = indstr.count("ArcsinF")
    nArccosF = indstr.count("ArccosF")
    nCosF = indstr.count("CosF")
    nSquareF = indstr.count("SquareF")
    nSqrtF = indstr.count("SqrtF")
    nAddP0 = indstr.count("AddP0")
    nAddP1 = indstr.count("AddP1")
    nAddP2 = indstr.count("AddP2")
    nSubP0 = indstr.count("SubP0")
    nSubP1 = indstr.count("SubP1")
    nSubP2 = indstr.count("SubP2")
    ndelP1 = indstr.count("delP1")
    ndelP2 = indstr.count("delP2")
    nMulP0 = indstr.count("MulP0")
    nMulP1 = indstr.count("MulP1")
    nMulP2 = indstr.count("MulP2")
    nMulD0 = indstr.count("MulD0")
    nMulD1 = indstr.count("MulD1")
    nMulD2 = indstr.count("MulD2")
    nCob0 = indstr.count("dP0")
    nCob1 = indstr.count("dP1")
    nCob0D = indstr.count("dD0")
    nCob1D = indstr.count("dD1")
    nStar0 = indstr.count("St0")
    nStar1 = indstr.count("St1")
    nStar2 = indstr.count("St2")
    nInvStar0 = indstr.count("InvSt0")
    nInvStar1 = indstr.count("InvSt1")
    nInvStar2 = indstr.count("InvSt2")
    nConst = indstr.count("1/2")
    nInn0 = indstr.count("Inn0")
    nInn1 = indstr.count("Inn1")
    nInn2 = indstr.count("Inn2")
    nsinF = indstr.count("SinF")
    ncosF = indstr.count("CosF")
    nexpF = indstr.count("ExpF")
    nlogF = indstr.count("LogF")
    nsqrtF = indstr.count("SqrtF")
    nSinP0 = indstr.count("SinP0")
    nSinP1 = indstr.count("SinP1")
    nSinP2 = indstr.count("SinP2")
    nSinD0 = indstr.count("SinD0")
    nSinD1 = indstr.count("SinD1")
    nSinD2 = indstr.count("SinD2")
    nArcsinP0 = indstr.count("ArcsinP0")
    nArcsinP1 = indstr.count("ArcsinP1")
    nArcsinP2 = indstr.count("ArcsinP2")
    nArcsinD0 = indstr.count("ArcsinD0")
    nArcsinD1 = indstr.count("ArcsinD1")
    nArcsinD2 = indstr.count("ArcsinD2")
    nCosP0 = indstr.count("CosP0")
    nCosP1 = indstr.count("CosP1")
    nCosP2 = indstr.count("CosP2")
    nCosD0 = indstr.count("CosD0")
    nCosD1 = indstr.count("CosD1")
    nCosD2 = indstr.count("CosD2")
    nArccosP0 = indstr.count("ArccosP0")
    nArccosP1 = indstr.count("ArccosP1")
    nArccosP2 = indstr.count("ArccosP2")
    nArccosD0 = indstr.count("ArccosD0")
    nArccosD1 = indstr.count("ArccosD1")
    nArccosD2 = indstr.count("ArccosD2")
    nExpP0 = indstr.count("ExpP0")
    nExpP1 = indstr.count("ExpP1")
    nExpP2 = indstr.count("ExpP2")
    nExpD0 = indstr.count("ExpD0")
    nExpD1 = indstr.count("ExpD1")
    nExpD2 = indstr.count("ExpD2")
    nLogP0 = indstr.count("LogP0")
    nLogP1 = indstr.count("LogP1")
    nLogP2 = indstr.count("LogP2")
    nLogD0 = indstr.count("LogD0")
    nLogD1 = indstr.count("LogD1")
    nLogD2 = indstr.count("LogD2")
    nSqrtP0 = indstr.count("SqrtP0")
    nSqrtP1 = indstr.count("SqrtP1")
    nSqrtP2 = indstr.count("SqrtP2")
    nSqrtD0 = indstr.count("SqrtD0")
    nSqrtD1 = indstr.count("SqrtD1")
    nSqrtD2 = indstr.count("SqrtD2")
    nSquareP0 = indstr.count("SquareP0")
    nSquareP1 = indstr.count("SquareP1")
    nSquareP2 = indstr.count("SquareP2")
    nSquareD0 = indstr.count("SquareD0")
    nSquareD1 = indstr.count("SquareD1")
    nSquareD2 = indstr.count("SquareD2")

    # Total objective value
    objval = total_err + reg_param*max((nAddP0, nMulFloat, nMulP0, nMulP1,
                                        nCob0, nConst, nAdd, nSub, nAddP1, nSubP0,
                                        nSubP1, ndelP1, ndelP2, nInn0, nInn1, nDiv,
                                        nAddP2, nSubP2, nMulP2, nMulD0, nMulD1, nMulD2,
                                        nCob1, nCob0D, nCob1D, nStar0, nStar1, nStar2,
                                        nInvStar0, nInvStar1, nInvStar2, nInn2, nsinF,
                                        ncosF, nexpF, nlogF, nsqrtF, nSinP0, nSinP1,
                                        nSinP2, nSinD0, nSinD1, nSinD2, nCosP0, nCosP1,
                                        nCosP2, nCosD0, nCosD1, nCosD2, nExpP0, nExpP1,
                                        nExpP2, nExpD0, nExpD1, nExpD2, nLogP0, nLogP1,
                                        nLogP2, nLogD0, nLogD1, nLogD2, nSqrtP0,
                                        nSqrtP1, nSqrtP2, nSqrtD0, nSqrtD1, nSqrtD2, nArcsinP0,
                                        nArcsinP1, nArcsinP2, nArcsinD0, nArcsinD1, nArcsinD2, nArccosP0,
                                        nArccosP1, nArccosP2, nArccosD0, nArccosD1, nArccosD2, nSquareP0,
                                        nSquareP1, nSquareP2, nSquareD0, nSquareD1, nSquareD2, nExpF, nLogF, nSinF,
                                        nArcsinF, nArccosF, nCosF, nSquareF, nSqrtF))
    # terminal_penalty = int("u" not in str(individual) or "fk" not in str(individual))
    # objval += length_penalty
    # objval += 100*terminal_penalty

    return objval,


# FIXME: maybe pass fitness function among parameters
GPproblem = gps.GPSymbRegProblem(pset,
                                 NINDIVIDUALS,
                                 NGEN,
                                 CXPB,
                                 MUTPB,
                                 stochastic_tournament={
                                     'enabled': True, 'prob': [0.7, 0.3]},
                                 tournsize=2,
                                 frac_elitist=frac_elitist)


# Register fitness function, selection and mutate operators
GPproblem.toolbox.register("mate", gp.cxOnePoint)
GPproblem.toolbox.register("expr_mut", gp.genGrow, min_=1, max_=3)
GPproblem.toolbox.register("mutate",
                           gp.mutUniform,
                           expr=GPproblem.toolbox.expr_mut,
                           pset=pset)

# Bloat control
GPproblem.toolbox.decorate(
    "mate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))
GPproblem.toolbox.decorate(
    "mutate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))

# Plot best solution


def plotSol(ind):
    u = eval_MSE(ind, X=X_train, y=y_train,
                 bvalues=bvalues_train, return_best_sol=True)
    plt.figure(10)
    fig = plt.gcf()
    fig.clear()
    plt.tricontourf(triang, u, cmap='RdBu', levels=20)
    plt.triplot(triang, 'ko-')
    plt.colorbar()
    fig.canvas.draw()
    plt.pause(0.05)


def stgp_poisson(config=None):

    early_stopping = {'enabled': True, 'max_overfit': 3}

    plot_best = True
    plot_best_genealogy = False

    # multiprocessing parameters
    n_jobs = 4
    n_splits = 20
    start_method = "fork"
    reg_param = 0.1

    if config is not None:
        GPproblem.NINDIVIDUALS = config["gp"]["NINDIVIDUALS"]
        GPproblem.NGEN = config["gp"]["NGEN"]
        n_jobs = config["mp"]["n_jobs"]
        n_splits = config["mp"]["n_splits"]
        start_method = config["mp"]["start_method"]
        early_stopping = config["gp"]["early_stopping"]
        reg_param = config["gp"]["reg_param"]
        min_ = config["gp"]["min_"]
        max_ = config["gp"]["max_"]
        GPproblem.parsimony_pressure = config["gp"]["parsimony_pressure"]
        GPproblem.tournsize = config["gp"]["select"]["tournsize"]
        GPproblem.stochastic_tournament = config["gp"]["select"]["stochastic_tournament"]
        mutate_fun = config["gp"]["mutate"]["fun"]
        mutate_kargs = eval(config["gp"]["mutate"]["kargs"])
        crossover_fun = config["gp"]["crossover"]["fun"]
        crossover_kargs = eval(config["gp"]["crossover"]["kargs"])
        expr_mut_fun = config["gp"]["mutate"]["expr_mut"]
        expr_mut_kargs = eval(config["gp"]["mutate"]["expr_mut_kargs"])
        num_sources = config["dataset"]["num_sources"]
        num_samples_per_source = config["dataset"]["num_samples_per_source"]
        noise_param = config["dataset"]["noise_param"]
        GPproblem.toolbox.register("mate", eval(crossover_fun), **crossover_kargs)
        GPproblem.toolbox.register("mutate",
                                   eval(mutate_fun), **mutate_kargs)
        GPproblem.toolbox.register("expr_mut", eval(expr_mut_fun), **expr_mut_kargs)
        GPproblem.toolbox.register("expr", gp.genHalfAndHalf,
                                   pset=pset, min_=min_, max_=max_)
        plot_best = config["plot"]["plot_best"]
        plot_best_genealogy = config["plot"]["plot_best_genealogy"]
        GPproblem.toolbox.decorate(
            "mate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))
        GPproblem.toolbox.decorate(
            "mutate", gp.staticLimit(key=operator.attrgetter("height"), max_value=17))

    start = time.perf_counter()

    # load dataset
    noise = noise_param*np.random.rand(num_nodes)
    data_X, data_y = d.generate_dataset(S, num_samples_per_source, num_sources, noise)
    X, y = d.split_dataset(data_X, data_y, 0.25, 0.25, use_validation)

    X_train, X_val, X_test = X
    y_train, y_val,  y_test = y
    # extract boundary values for the test set
    bvalues_test = X_test[:, bnodes]
    # extract bvalues_train
    bvalues_train = X_train[:, bnodes]
    bvalues_val = X_val[:, bnodes]

    # add functions for fitness evaluation (value of the objective function) on training
    # set and MSE evaluation on validation set
    GPproblem.toolbox.register("evaluate_train",
                               eval_fitness,
                               X=X_train,
                               y=y_train,
                               bvalues=bvalues_train,
                               reg_param=reg_param)
    GPproblem.toolbox.register("evaluate_val_fit",
                               eval_fitness,
                               X=X_val,
                               y=y_val,
                               bvalues=bvalues_val,
                               reg_param=reg_param)
    GPproblem.toolbox.register("evaluate_val_MSE",
                               eval_MSE,
                               X=X_val,
                               y=y_val,
                               bvalues=bvalues_val)

    print("> MODEL TRAINING/SELECTION STARTED", flush=True)
    # train the model in the training set
    pool = mpire.WorkerPool(n_jobs=n_jobs, start_method=start_method)
    GPproblem.toolbox.register("map", pool.map)
    GPproblem.run(plot_history=True,
                  print_log=True,
                  plot_best=plot_best,
                  plot_best_func=plotSol,
                  plot_best_genealogy=plot_best_genealogy,
                  seed=None,
                  n_splits=n_splits,
                  early_stopping=early_stopping)

    # Print best individual
    best = GPproblem.best
    print(f"The best individual is {str(best)}", flush=True)

    # evaluate score on the training and validation set
    print(f"The best fitness on the training set is {GPproblem.min_fit_history[-1]}")
    print(f"The best MSE on the validation set is {GPproblem.min_valerr}")

    print("> MODEL TRAINING/SELECTION COMPLETED", flush=True)

    score_test = eval_MSE(best, X_test, y_test, bvalues_test)
    print(f"The best MSE on the test set is {score_test}")

    print(f"Elapsed time: {round(time.perf_counter() - start, 2)}")

    # plot the tree of the best individual
    nodes, edges, labels = gp.graph(best)
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    pos = nx.nx_agraph.graphviz_layout(graph, prog="dot")

    plt.figure(figsize=(7, 7))
    nx.draw_networkx_nodes(graph, pos, node_size=900, node_color="w")
    nx.draw_networkx_edges(graph, pos)
    nx.draw_networkx_labels(graph, pos, labels)
    plt.axis("off")
    plt.show()


if __name__ == '__main__':
    n_args = len(sys.argv)
    config = None
    if n_args > 1:
        param_file = sys.argv[1]
        print("Parameters file: ", param_file)
        with open(param_file) as file:
            config = yaml.safe_load(file)
            print(yaml.dump(config))
    stgp_poisson(config)
