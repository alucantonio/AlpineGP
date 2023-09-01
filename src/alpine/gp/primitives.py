import jax.numpy as jnp
from deap import gp
from dctkit.dec import cochain as C
import dctkit as dt
from typing import List, Dict, Callable, Tuple
from functools import partial
import operator


def protectedDiv(left, right):
    try:
        return jnp.divide(left, right)
    except ZeroDivisionError:
        return jnp.nan


def protectedLog(x):
    try:
        return jnp.log(x)
    except ValueError:
        return jnp.nan


def protectedSqrt(x):
    try:
        return jnp.sqrt(x)
    except ValueError:
        return jnp.nan


def inv_float(x):
    return protectedDiv(1., x)


def inv_scalar_mul(c, f):
    try:
        return C.scalar_mul(c, 1/f)
    except ZeroDivisionError:
        return C.scalar_mul(c, jnp.nan)


def square_mod(x):
    return jnp.square(x).astype(dt.float_dtype)


class PrimitiveParams:
    def __init__(self, op, in_types, out_type) -> None:
        self.op = op
        self.in_types = in_types
        self.out_type = out_type


'''
primitives = {
    # scalar operations
    'Add': PrimitiveParams(jnp.add, [float, float], float),
    'Sub': PrimitiveParams(jnp.subtract, [float, float], float),
    'MulF': PrimitiveParams(jnp.multiply, [float, float], float),
    'Div': PrimitiveParams(protectedDiv, [float, float], float),
    'SinF': PrimitiveParams(jnp.sin, [float], float),
    'ArcsinF': PrimitiveParams(jnp.arcsin, [float], float),
    'CosF': PrimitiveParams(jnp.cos, [float], float),
    'ArccosF': PrimitiveParams(jnp.arccos, [float], float),
    'ExpF': PrimitiveParams(jnp.exp, [float], float),
    'LogF': PrimitiveParams(protectedLog, [float], float),
    'SqrtF': PrimitiveParams(protectedSqrt, [float], float),
    'SquareF': PrimitiveParams(square_mod, [float], float),
    'InvF': PrimitiveParams(inv_float, [float], float),
    # cochain operations
    'AddP0': PrimitiveParams(C.add, [C.CochainP0, C.CochainP0], C.CochainP0),
    'AddP1': PrimitiveParams(C.add, [C.CochainP1, C.CochainP1], C.CochainP1),
    'AddP2': PrimitiveParams(C.add, [C.CochainP2, C.CochainP2], C.CochainP2),
    'AddD0': PrimitiveParams(C.add, [C.CochainD0, C.CochainD0], C.CochainD0),
    'AddD1': PrimitiveParams(C.add, [C.CochainD1, C.CochainD1], C.CochainD1),
    'AddD2': PrimitiveParams(C.add, [C.CochainD2, C.CochainD2], C.CochainD2),
    'SubP0': PrimitiveParams(C.sub, [C.CochainP0, C.CochainP0], C.CochainP0),
    'SubP1': PrimitiveParams(C.sub, [C.CochainP1, C.CochainP1], C.CochainP1),
    'SubP2': PrimitiveParams(C.sub, [C.CochainP2, C.CochainP2], C.CochainP2),
    'SubD0': PrimitiveParams(C.sub, [C.CochainD0, C.CochainD0], C.CochainD0),
    'SubD1': PrimitiveParams(C.sub, [C.CochainD1, C.CochainD1], C.CochainD1),
    'SubD2': PrimitiveParams(C.sub, [C.CochainD2, C.CochainD2], C.CochainD2),

    'dP0': PrimitiveParams(C.coboundary, [C.CochainP0], C.CochainP1),
    'dP1': PrimitiveParams(C.coboundary, [C.CochainP1], C.CochainP2),
    'dD0': PrimitiveParams(C.coboundary, [C.CochainD0], C.CochainD1),
    'dD1': PrimitiveParams(C.coboundary, [C.CochainD1], C.CochainD2),
    'delP1': PrimitiveParams(C.codifferential, [C.CochainP1], C.CochainP0),
    'delP2': PrimitiveParams(C.codifferential, [C.CochainP2], C.CochainP1),
    'delD1': PrimitiveParams(C.codifferential, [C.CochainD1], C.CochainD0),
    'delD2': PrimitiveParams(C.codifferential, [C.CochainD2], C.CochainD1),
    'LapP0': PrimitiveParams(C.laplacian, [C.CochainP0], C.CochainP0),

    'St0d1': PrimitiveParams(C.star, [C.CochainP0], C.CochainD1),
    'St0d2': PrimitiveParams(C.star, [C.CochainP0], C.CochainD2),
    'St1d1': PrimitiveParams(C.star, [C.CochainP1], C.CochainD0),
    'St1d2': PrimitiveParams(C.star, [C.CochainP1], C.CochainD1),
    'St2d2': PrimitiveParams(C.star, [C.CochainP2], C.CochainD0),
    'InvSt0d1': PrimitiveParams(C.star, [C.CochainD1], C.CochainP0),
    'InvSt0d2': PrimitiveParams(C.star, [C.CochainD2], C.CochainP0),
    'InvSt1d1': PrimitiveParams(C.star, [C.CochainD0], C.CochainP1),
    'InvSt1d2': PrimitiveParams(C.star, [C.CochainD1], C.CochainP1),
    'InvSt2d2': PrimitiveParams(C.star, [C.CochainD0], C.CochainP2),

    'MulP0': PrimitiveParams(C.scalar_mul, [C.CochainP0, float], C.CochainP0),
    'MulP1': PrimitiveParams(C.scalar_mul, [C.CochainP1, float], C.CochainP1),
    'MulP2': PrimitiveParams(C.scalar_mul, [C.CochainP2, float], C.CochainP2),
    'MulD0': PrimitiveParams(C.scalar_mul, [C.CochainD0, float], C.CochainD0),
    'MulD1': PrimitiveParams(C.scalar_mul, [C.CochainD1, float], C.CochainD1),
    'MulD2': PrimitiveParams(C.scalar_mul, [C.CochainD2, float], C.CochainD2),
    'InvMulP0': PrimitiveParams(inv_scalar_mul, [C.CochainP0, float], C.CochainP0),
    'InvMulP1': PrimitiveParams(inv_scalar_mul, [C.CochainP1, float], C.CochainP1),
    'InvMulP2': PrimitiveParams(inv_scalar_mul, [C.CochainP2, float], C.CochainP2),
    'InvMulD0': PrimitiveParams(inv_scalar_mul, [C.CochainD0, float], C.CochainD0),
    'InvMulD1': PrimitiveParams(inv_scalar_mul, [C.CochainD1, float], C.CochainD1),
    'InvMulD2': PrimitiveParams(inv_scalar_mul, [C.CochainD2, float], C.CochainD2),

    'CochMulP0': PrimitiveParams(C.cochain_mul, [C.CochainP0, C.CochainP0],
                                 C.CochainP0),
    'CochMulP1': PrimitiveParams(C.cochain_mul, [C.CochainP1, C.CochainP1],
                                 C.CochainP1),
    'CochMulP2': PrimitiveParams(C.cochain_mul, [C.CochainP2, C.CochainP2],
                                 C.CochainP2),
    'CochMulD0': PrimitiveParams(C.cochain_mul, [C.CochainD0, C.CochainD0],
                                 C.CochainD0),
    'CochMulD1': PrimitiveParams(C.cochain_mul, [C.CochainD1, C.CochainD1],
                                 C.CochainD1),
    'CochMulD2': PrimitiveParams(C.cochain_mul, [C.CochainD2, C.CochainD2],
                                 C.CochainD2),

    'InnP0': PrimitiveParams(C.inner_product, [C.CochainP0, C.CochainP0], float),
    'InnP1': PrimitiveParams(C.inner_product, [C.CochainP1, C.CochainP1], float),
    'InnP2': PrimitiveParams(C.inner_product, [C.CochainP2, C.CochainP2], float),
    'InnD0': PrimitiveParams(C.inner_product, [C.CochainD0, C.CochainD0], float),
    'InnD1': PrimitiveParams(C.inner_product, [C.CochainD1, C.CochainD1], float),
    'InnD2': PrimitiveParams(C.inner_product, [C.CochainD2, C.CochainD2], float),

    'SinP0': PrimitiveParams(C.sin, [C.CochainP0], C.CochainP0),
    'SinP1': PrimitiveParams(C.sin, [C.CochainP1], C.CochainP1),
    'SinP2': PrimitiveParams(C.sin, [C.CochainP2], C.CochainP2),
    'SinD0': PrimitiveParams(C.sin, [C.CochainD0], C.CochainD0),
    'SinD1': PrimitiveParams(C.sin, [C.CochainD1], C.CochainD1),
    'SinD2': PrimitiveParams(C.sin, [C.CochainD2], C.CochainD2),

    'ArcsinP0': PrimitiveParams(C.arcsin, [C.CochainP0], C.CochainP0),
    'ArcsinP1': PrimitiveParams(C.arcsin, [C.CochainP1], C.CochainP1),
    'ArcsinP2': PrimitiveParams(C.arcsin, [C.CochainP2], C.CochainP2),
    'ArcsinD0': PrimitiveParams(C.arcsin, [C.CochainD0], C.CochainD0),
    'ArcsinD1': PrimitiveParams(C.arcsin, [C.CochainD1], C.CochainD1),
    'ArcsinD2': PrimitiveParams(C.arcsin, [C.CochainD2], C.CochainD2),

    'CosP0': PrimitiveParams(C.cos, [C.CochainP0], C.CochainP0),
    'CosP1': PrimitiveParams(C.cos, [C.CochainP1], C.CochainP1),
    'CosP2': PrimitiveParams(C.cos, [C.CochainP2], C.CochainP2),
    'CosD0': PrimitiveParams(C.cos, [C.CochainD0], C.CochainD0),
    'CosD1': PrimitiveParams(C.cos, [C.CochainD1], C.CochainD1),
    'CosD2': PrimitiveParams(C.cos, [C.CochainD2], C.CochainD2),

    'ArccosP0': PrimitiveParams(C.arccos, [C.CochainP0], C.CochainP0),
    'ArccosP1': PrimitiveParams(C.arccos, [C.CochainP1], C.CochainP1),
    'ArccosP2': PrimitiveParams(C.arccos, [C.CochainP2], C.CochainP2),
    'ArccosD0': PrimitiveParams(C.arccos, [C.CochainD0], C.CochainD0),
    'ArccosD1': PrimitiveParams(C.arccos, [C.CochainD1], C.CochainD1),
    'ArccosD2': PrimitiveParams(C.arccos, [C.CochainD2], C.CochainD2),

    'ExpP0': PrimitiveParams(C.exp, [C.CochainP0], C.CochainP0),
    'ExpP1': PrimitiveParams(C.exp, [C.CochainP1], C.CochainP1),
    'ExpP2': PrimitiveParams(C.exp, [C.CochainP2], C.CochainP2),
    'ExpD0': PrimitiveParams(C.exp, [C.CochainD0], C.CochainD0),
    'ExpD1': PrimitiveParams(C.exp, [C.CochainD1], C.CochainD1),
    'ExpD2': PrimitiveParams(C.exp, [C.CochainD2], C.CochainD2),

    'LogP0': PrimitiveParams(C.log, [C.CochainP0], C.CochainP0),
    'LogP1': PrimitiveParams(C.log, [C.CochainP1], C.CochainP1),
    'LogP2': PrimitiveParams(C.log, [C.CochainP2], C.CochainP2),
    'LogD0': PrimitiveParams(C.log, [C.CochainD0], C.CochainD0),
    'LogD1': PrimitiveParams(C.log, [C.CochainD1], C.CochainD1),
    'LogD2': PrimitiveParams(C.log, [C.CochainD2], C.CochainD2),

    'SqrtP0': PrimitiveParams(C.sqrt, [C.CochainP0], C.CochainP0),
    'SqrtP1': PrimitiveParams(C.sqrt, [C.CochainP1], C.CochainP1),
    'SqrtP2': PrimitiveParams(C.sqrt, [C.CochainP2], C.CochainP2),
    'SqrtD0': PrimitiveParams(C.sqrt, [C.CochainD0], C.CochainD0),
    'SqrtD1': PrimitiveParams(C.sqrt, [C.CochainD1], C.CochainD1),
    'SqrtD2': PrimitiveParams(C.sqrt, [C.CochainD2], C.CochainD2),

    'SquareP0': PrimitiveParams(C.square, [C.CochainP0], C.CochainP0),
    'SquareP1': PrimitiveParams(C.square, [C.CochainP1], C.CochainP1),
    'SquareP2': PrimitiveParams(C.square, [C.CochainP2], C.CochainP2),
    'SquareD0': PrimitiveParams(C.square, [C.CochainD0], C.CochainD0),
    'SquareD1': PrimitiveParams(C.square, [C.CochainD1], C.CochainD1),
    'SquareD2': PrimitiveParams(C.square, [C.CochainD2], C.CochainD2)
}
'''


# FIXME: continue the docs


def generate_primitive(primitive: Dict[str, Dict[str, Callable] | List[str] | str | Dict]) -> Dict:
    """Generate all the primitives given a typed function.

    Args:
        primitive: a dictionary containing the relevant information of the function.
          It consists of the following 5 keys: 'fun_info' contains an inner dictionary
          encoding the name of the function (value of the inner key 'name') and the
          callable itself (value of the inner key 'fun'); 'input' contains a list
          composed of the input types; 'output' contains a string encoding the output
          type; 'att_input' contains an inner dictionary with keys 'category'
          (primal/dual), 'dimension' (0,1,2) and 'rank' ("SC", i.e. scalar, "V", "T"
          or "VT"); 'map_output' contains an inner dictionary consisting of the
          same keys of 'att_input'. In this case, each key contains a callable object
          that provides the map to get the output category/dimension/rank given the
          input one.

    Returns:
        a dict in which each key is the name of the sub-primitive and each value
            is a PrimitiveParams object.
    """
    general_primitive = primitive['fun_info']
    in_attribute = primitive['att_input']
    max_dim = int(list(in_attribute['dimension'])[-1])
    map_rule = primitive['map_rule']
    primitive_dictionary = dict()
    for in_category in in_attribute['category']:
        for in_dim in in_attribute['dimension']:
            for in_rank in in_attribute['rank']:
                # concatenation of strings
                in_rank = in_rank.replace("SC", "")
                primitive_name = general_primitive['name'] + \
                    in_category + in_dim + in_rank
                in_type_name = []
                for i, input in enumerate(primitive['input']):
                    # float type must be handled separately
                    if input == "float":
                        in_type_name.append(input)
                    elif len(in_rank) == 2:
                        # in this case the correct rank must be taken
                        in_type_name.append(input + in_category +
                                            in_dim + in_rank[i])
                    else:
                        in_type_name.append(input + in_category + in_dim + in_rank)
                in_type = list(map(eval, in_type_name))
                out_category = map_rule['category'](in_category)
                # for star dimension mapping is delicate
                if general_primitive['name'] == "St":
                    out_dim = str(map_rule['dimension'](int(in_dim), max_dim))
                else:
                    out_dim = str(map_rule['dimension'](int(in_dim)))
                out_rank = map_rule['rank'](in_rank)
                out_type_name = primitive['output'] + out_category + out_dim + out_rank
                out_type = eval(out_type_name)
                primitive_dictionary[primitive_name] = PrimitiveParams(
                    general_primitive['fun'], in_type, out_type)
    return primitive_dictionary


def switch_category(categories: Tuple, category: str):
    switched_category_list = list(set(categories) - set(category))
    return str(switched_category_list[0])


def identity(x):
    return x


def empty_string(x):
    return ""


def rank_downgrade(x):
    if x == "T":
        return "V"
    elif x == "V":
        return ""
    raise ValueError("Invalid input rank")


def vec_tensor_mul_rank(x):
    return "T"


def star_dim(x, max_dim):
    return max_dim - x


scalar_primitives = {
    # scalar operations
    'AddF': PrimitiveParams(jnp.add, [float, float], float),
    'SubF': PrimitiveParams(jnp.subtract, [float, float], float),
    'MulF': PrimitiveParams(jnp.multiply, [float, float], float),
    'Div': PrimitiveParams(protectedDiv, [float, float], float),
    'SinF': PrimitiveParams(jnp.sin, [float], float),
    'ArcsinF': PrimitiveParams(jnp.arcsin, [float], float),
    'CosF': PrimitiveParams(jnp.cos, [float], float),
    'ArccosF': PrimitiveParams(jnp.arccos, [float], float),
    'ExpF': PrimitiveParams(jnp.exp, [float], float),
    'LogF': PrimitiveParams(protectedLog, [float], float),
    'SqrtF': PrimitiveParams(protectedSqrt, [float], float),
    'SquareF': PrimitiveParams(square_mod, [float], float),
    'InvF': PrimitiveParams(inv_float, [float], float)}
coch_primitives = []
primitives = scalar_primitives
add_coch = {'fun_info': {'name': 'AddC', 'fun': C.add},
            'input': ["C.Cochain", "C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC", "V", "T")},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(add_coch))
sub_coch = {'fun_info': {'name': 'SubC', 'fun': C.sub},
            'input': ["C.Cochain", "C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC", "V", "T")},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(sub_coch))
coboundary = {'fun_info': {'name': 'd', 'fun': C.coboundary},
              'input': ["C.Cochain"],
              'output': "C.Cochain",
              'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1'), "rank": ("SC",)},
              'map_rule': {'category': identity, 'dimension': partial(operator.add, 1), "rank": identity}}
coch_primitives.append(generate_primitive(coboundary))
codifferential = {'fun_info': {'name': 'del', 'fun': C.codifferential},
                  'input': ["C.Cochain"],
                  'output': "C.Cochain",
                  'att_input': {'category': ('P', 'D'), 'dimension': ('1', '2'), "rank": ("SC",)},
                  'map_rule': {'category': identity, 'dimension': partial(operator.add, -1), "rank": identity}}
coch_primitives.append(generate_primitive(codifferential))
tr_coch = {'fun_info': {'name': 'tr', 'fun': C.trace},
           'input': ["C.Cochain"],
           'output': "C.Cochain",
           'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("T",)},
           'map_rule': {'category': identity, 'dimension': identity, "rank": rank_downgrade}}
coch_primitives.append(generate_primitive(tr_coch))
mul_FT = {'fun_info': {'name': 'MF', 'fun': C.scalar_mul},
          'input': ["C.Cochain", "float"],
          'output': "C.Cochain",
          'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC", "T")},
          'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(mul_FT))
mul_coch = {'fun_info': {'name': 'CMul', 'fun': C.cochain_mul},
            'input': ["C.Cochain", "C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(mul_coch))
mul_VT = {'fun_info': {'name': 'Mv', 'fun': C.vector_tensor_mul},
          'input': ["C.Cochain", "C.Cochain"],
          'output': "C.Cochain",
          'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("VT",)},
          'map_rule': {'category': identity, 'dimension': identity, "rank": vec_tensor_mul_rank}}
coch_primitives.append(generate_primitive(mul_VT))
tran_coch = {'fun_info': {'name': 'tran', 'fun': C.transpose},
             'input': ["C.Cochain"],
             'output': "C.Cochain",
             'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("T",)},
             'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(tran_coch))
star = {'fun_info': {'name': 'St', 'fun': C.star},
        'input': ["C.Cochain"],
        'output': "C.Cochain",
        'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC", "T")},
        'map_rule': {'category': partial(switch_category, ('P', 'D')), 'dimension': star_dim, "rank": identity}}
coch_primitives.append(generate_primitive(star))
inner_product = {'fun_info': {'name': 'Inn', 'fun': C.inner_product},
                 'input': ["C.Cochain", "C.Cochain"],
                 'output': "float",
                 'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC", "T")},
                 'map_rule': {'category': empty_string, 'dimension': empty_string, "rank": empty_string}}
coch_primitives.append(generate_primitive(inner_product))
sin_coch = {'fun_info': {'name': 'Sin', 'fun': C.sin},
            'input': ["C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(sin_coch))
arcsin_coch = {'fun_info': {'name': 'ArcSin', 'fun': C.arcsin},
               'input': ["C.Cochain"],
               'output': "C.Cochain",
               'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
               'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(arcsin_coch))
cos_coch = {'fun_info': {'name': 'Cos', 'fun': C.cos},
            'input': ["C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(cos_coch))
arccos_coch = {'fun_info': {'name': 'ArcCos', 'fun': C.arccos},
               'input': ["C.Cochain"],
               'output': "C.Cochain",
               'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
               'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(arccos_coch))
exp_coch = {'fun_info': {'name': 'Exp', 'fun': C.exp},
            'input': ["C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(exp_coch))
log_coch = {'fun_info': {'name': 'Log', 'fun': C.log},
            'input': ["C.Cochain"],
            'output': "C.Cochain",
            'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
            'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(log_coch))
sqrt_coch = {'fun_info': {'name': 'Sqrt', 'fun': C.sqrt},
             'input': ["C.Cochain"],
             'output': "C.Cochain",
             'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
             'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(sqrt_coch))
square_coch = {'fun_info': {'name': 'Square', 'fun': C.square},
               'input': ["C.Cochain"],
               'output': "C.Cochain",
               'att_input': {'category': ('P', 'D'), 'dimension': ('0', '1', '2'), "rank": ("SC",)},
               'map_rule': {'category': identity, 'dimension': identity, "rank": identity}}
coch_primitives.append(generate_primitive(square_coch))


for primitive in coch_primitives:
    # merge dictionary
    primitives = primitives | primitive
primitives = scalar_primitives | primitives


def addPrimitivesToPset(pset: gp.PrimitiveSetTyped,
                        primitive_spec: List | None = None) -> None:

    for primitive_family in primitive_spec:
        non_feasible_dimensions = list(set(('0', '1', '2')) -
                                       set(primitive_family['dimension']))
        non_feasible_ranks = list(
            set(("SC", "V", "T", "vtm")) - set(primitive_family["rank"]))
        non_feasible_objects = non_feasible_dimensions + non_feasible_ranks
        for primitive in primitives.keys():
            if primitive_family['name'] in primitive:
                if sum([primitive_family['name'].count(obj)
                        for obj in non_feasible_objects]) == 0 or primitive_family['name'].count("VT") == 1:
                    # check that it's of a feasible dimension
                    op = primitives[primitive].op
                    in_types = primitives[primitive].in_types
                    out_type = primitives[primitive].out_type
                    pset.addPrimitive(op, in_types, out_type, name=primitive)
