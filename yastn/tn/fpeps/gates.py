import numpy as np
from typing import NamedTuple
from ... import ncon, eye, tensordot


class Gate_nn(NamedTuple):
    """ A should be before B in the fermionic order. """
    A : tuple = None
    B : tuple = None
    bond : tuple = None


class Gate_local(NamedTuple):
    A : tuple = None
    site : tuple = None


class Gates(NamedTuple):
    nn : list = None   # list of NN gates
    local : list = None   # list of local gates


def match_ancilla(gate, top, swap=False):
    """ kron and fusion of local gate with identity for ancilla. Identity is read from ancila of A. """
    leg = top.get_legs(axes=-1)

    if not leg.is_fused():
        return gate

    _, leg = leg.unfuse_leg()  # unfuse to get ancilla leg
    one = eye(config=top.config, legs=[leg, leg.conj()], isdiag=False)
    new_gate = tensordot(gate, one, axes=((), ()))

    if gate.ndim == 2:
        return new_gate.fuse_legs(axes=((0, 2), (1, 3)))
    # else gate.ndim == 3:
    if swap:
        new_gate = new_gate.swap_gate(axes=(2, 3))
    return new_gate.fuse_legs(axes=((0, 3), (1, 4), 2))


def decompose_nn_gate(Gnn):
    U, S, V = Gnn.svd_with_truncation(axes=((0, 2), (1, 3)), sU=-1, tol=1e-14, Vaxis=2)
    S = S.sqrt()
    return Gate_nn(S.broadcast(U, axes=2), S.broadcast(V, axes=2))


def gate_nn_hopping(t, step, I, c, cdag):
    """
    Nearest-neighbor gate G = exp(-step * H)
    for H = -t * (cdag1 c2 + c2dag c1)

    G = I + (cosh(x) - 1) * (n1 + n2 - 2 n1 n2) + sinh(x) * (c1dag c2 + c2dag c1)
    """
    n = cdag @ c
    II = ncon([I, I], [(-0, -2), (-1, -3)])
    n1 = ncon([n, I], [(-0, -2), (-1, -3)])
    n2 = ncon([I, n], [(-0, -2), (-1, -3)])
    nn = ncon([n, n], [(-0, -2), (-1, -3)])

    # site-1 is before site-2 in fermionic order
    # c1dag c2;
    c1dag = cdag.add_leg(s=1).swap_gate(axes=(0, 2))
    c2 = c.add_leg(s=-1)
    cc = ncon([c1dag, c2], [(-0, -2, 1) , (-1, -3, 1)])

    # c2dag c1
    c1 = c.add_leg(s=1).swap_gate(axes=(1, 2))
    c2dag = cdag.add_leg(s=-1)
    cc = cc + ncon([c1, c2dag], [(-0, -2, 1) , (-1, -3, 1)])

    G =  II + (np.cosh(t * step) - 1) * (n1 + n2 - 2 * nn) + np.sinh(t * step) * cc
    return decompose_nn_gate(G)


# def Hamiltonian_nn_hopping():
#     #  c1 dag c2 + c2dag c1
#     pass
#     c1 = c.add_leg(s=1).swap_gate(axes=(1, 2))
#     c2dag = cdag.add_leg(s=-1)
#     cc = cc + ncon([c1, c2dag], [(-0, -2, 1) , (-1, -3, 1)])
#     return decompose_nn_gate(cc)



def gate_local_Coulomb(mu_up, mu_dn, U, step, I, n_up, n_dn):
    """
    Local gate exp(-step * H)
    for H = U * (n_up - I / 2) * (n_dn - I / 2) - mu_up * n_up - mu_dn * n_dn

    We ignore a constant U / 4 in the above Hamiltonian.
    """
    nn = n_up @ n_dn
    G_loc = I
    G_loc = G_loc + (n_dn - nn) * (np.exp(step * (mu_dn + U / 2)) - 1)
    G_loc = G_loc + (n_up - nn) * (np.exp(step * (mu_up + U / 2)) - 1)
    G_loc = G_loc + nn * (np.exp(step * (mu_up + mu_dn)) - 1)
    return Gate_local(G_loc)


# def Hamiltonian_local_Coulomb(n_up, n_dn):
#     return Gate_local(n_up @ n_dn)

def gate_local_occupation(mu, step, I, n):
    """
    Local gate exp(-step * H)
    for H = -mu * n
    """
    return Gate_local(I + n * (np.exp(mu * step) - 1))


def distribute(geometry, gates_nn=None, gates_local=None) -> Gates:
    """
    Distributes gates homogeneous over the lattice.

    Parameters
    ----------
    geomtry : yastn.tn.fpeps.SquareLattice | yastn.tn.fpeps.CheckerboardLattice | yast.tn.fpeps.Peps
        Geometry of PEPS lattice.
        Can be any structure that includes geometric information about the lattice, like the Peps class.

    nn : Gate_nn | Sequence[Gate_nn]
        Nearest-neighbor gate, or a list of gates, to be distributed over lattice bonds.

    local : Gate_local | Sequence[Gate_local]
        Local gate, or a list of local gates, to be distributed over lattice sites.
    """

    if isinstance(gates_nn, Gate_nn):
        gates_nn = [gates_nn]

    nn = []
    if gates_nn is not None:
        for bond in geometry.bonds():
            for Gnn in gates_nn:
                nn.append(Gnn._replace(bond=bond))

    if isinstance(gates_local, Gate_local):
        gates_local = [gates_local]

    local = []
    if gates_local is not None:
        for site in geometry.sites():
            for Gloc in gates_local:
                local.append(Gloc._replace(site=site))

    return Gates(nn=nn, local=local)


def gate_product_operator(O0, O1, l_ordered=True, f_ordered=True, merge=False):
    """
    Takes two ndim=2 local operators O0 O1, with O1 acting first (relevant for fermionic operators).
    Adds a connecting leg with a swap_gate consistent with fermionic order.
    Orders output to match lattice order.

    If merge, returns equivalnt of ncon([O0, O1], [(-0, -2), (-1, -3)]),
    with proper operator order and swap-gate applied.
    """
    G0 = O0.add_leg(s=1)
    G1 = O1.add_leg(s=-1)
    if f_ordered:
        G0 = G0.swap_gate(axes=(0, 2))
    else:
        G1 = G1.swap_gate(axes=(1, 2))

    if not l_ordered or l_ordered in ('rl', 'bt'):
        G0, G1 = G1, G0

    if merge:
        return tensordot(G0, G1, axes=(2, 2)).transpose(axes=(0, 2, 1, 3))
    return G0, G1


def gate_fix_order(G0, G1, l_ordered=True, f_ordered=True):
    """
    Modifies two gate tensors, that were generated consitent with lattice and fermionic orders,
    to make them consistent with provided ordere.
    """
    if not f_ordered:
        G0 = G0.swap_gate(axes=(0, 2))
        G1 = G1.swap_gate(axes=(1, 2))
    if not l_ordered or l_ordered in ('rl', 'bt'):
        G0, G1 = G1, G0
    return G0, G1



def apply_gate(ten, op, dirn=None):
    """
    Prepare top and bottom peps tensors for CTM procedures.
    Applies operators on top if provided, with dir = 'l', 'r', 't', 'b', '1s'.
    If dirn is None, no auxiliary indices are introduced as the operator is local.
    Spin and ancilla legs of tensors are always fused.
    """
    swap = dirn is not None and dirn in 'tl'
    op = match_ancilla(op, ten, swap=swap)
    Ao = tensordot(ten, op, axes=(2, 1)) # [t l] [b r] [s a] c

    if dirn is None:
        return Ao
    if dirn == 't':
        Ao = Ao.unfuse_legs(axes=1) # [t l] b r [s a] c
        Ao = Ao.fuse_legs(axes=(0, (1, 4), 2, 3)) # [t l] [b c] r [s a]
        return Ao.fuse_legs(axes=(0, (1, 2), 3)) # [t l] [[b c] r] [s a]
    if dirn == 'b':
        Ao = Ao.unfuse_legs(axes=0) # t l [b r] [s a] c
        Ao = Ao.swap_gate(axes=(1, 4))
        Ao = Ao.fuse_legs(axes=((0, 4), 1, 2, 3)) # [t c] l [b r] [s a]
        return Ao.fuse_legs(axes=((0, 1), 2, 3)) # [[t c] l] [b r] [s a]
    if dirn == 'l':
        Ao = Ao.unfuse_legs(axes=1) # [t l] b r [s a] c
        Ao = Ao.swap_gate(axes=(1, 4))
        Ao = Ao.fuse_legs(axes=(0, 1, (2, 4), 3)) # [t l] b [r c] [s a]
        return Ao.fuse_legs(axes=(0, (1, 2), 3)) # [t l] [b [r c]] [s a]
    if dirn == 'r':
        Ao = Ao.unfuse_legs(axes=0) # t l [b r] [s a] c
        Ao = Ao.fuse_legs(axes=(0, (1, 4), 2, 3)) # t [l c] [b r] [s a]
        return Ao.fuse_legs(axes=((0, 1), 2, 3)) # [t [l c]] [b r] [s a]
    raise RuntimeError("dirn should be equal to 'l', 'r', 't', 'b', or None")
