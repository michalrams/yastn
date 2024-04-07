""" Basic structures forming PEPS network. """
from itertools import product
from typing import NamedTuple
from ... import YastnError


class Site(NamedTuple):
    nx : int = 0
    ny : int = 0

    def __str__(self):
        return f"Site({self.nx},{self.ny})"


class Bond(NamedTuple):  # Not very convinient to use
    """
    A bond between two lattice sites.

    site0 should preceed site1 in the fermionic order.
    """
    site0 : Site = None
    site1 : Site = None

    def __str__(self):
        return f"Bond(({self.site0.nx},{self.site0.ny}),({self.site1.nx},{self.site1.ny}))"


    @property
    def dirn(self):
        """
        Bond direction.

        Return 'h' when site0.nx == site1.nx.
        Otherwise return 'v' when, by construction, site0.ny == site1.ny.
        """
        return 'h' if self.site0[0] == self.site1[0] else 'v'


_periodic_dict = {'infinite': 'ii', 'obc': 'oo', 'cylinder': 'po'}

class SquareLattice():

    def __init__(self, dims=(2, 2), boundary='infinite'):
        r"""
        Geometric information about 2D square lattice.

        Parameters
        ----------
        dims : tuple[int, int]
            Size of elementary cell.
        boundary : str
            'obc', 'infinite', or 'cylinder'.

        Notes
        -----
        Site(0, 0) corresponds to top-left corner of the lattice.
        """
        if boundary not in ('obc', 'infinite', 'cylinder'):
            raise YastnError("boundary should be 'obc', 'infinite', or 'cylinder'")

        self.boundary = boundary
        self._periodic = _periodic_dict[boundary]
        self._dims = (dims[0], dims[1])
        self._sites = tuple(Site(nx, ny) for ny in range(self._dims[1]) for nx in range(self._dims[0]))
        self._dir = {'tl': (-1, -1), 't': (-1, 0), 'tr': (-1,  1),
                      'l': ( 0, -1),                'r': ( 0,  1),
                     'bl': ( 1, -1), 'b': ( 1, 0), 'br': ( 1,  1)}

        bonds_h, bonds_v = [], []
        for s in self._sites:
            s_r = self.nn_site(s, d='r')  # left is before right in the fermionic order
            if s_r is not None:
                bonds_h.append(Bond(s, s_r))
            s_b = self.nn_site(s, d='b')  # top is before bottom in the fermionic order
            if s_b is not None:
                bonds_v.append(Bond(s, s_b))
        self._bonds_h = tuple(bonds_h)
        self._bonds_v = tuple(bonds_v)

    @property
    def Nx(self):
        return self._dims[0]

    @property
    def Ny(self):
        return self._dims[1]

    @property
    def dims(self):
        """ Size of the unit cell. """
        return self._dims

    def sites(self, reverse=False):
        """ Sequence of unique lattice sites. """
        return self._sites[::-1] if reverse else self._sites

    def bonds(self, dirn=None, reverse=False):
        """ Sequence of unique nearest neighbor bonds between lattice sites. """
        if dirn == 'v':
            return self._bonds_v[::-1] if reverse else self._bonds_v
        if dirn == 'h':
            return self._bonds_h[::-1] if reverse else self._bonds_h
        return self._bonds_v[::-1] + self._bonds_h[::-1] if reverse else self._bonds_h + self._bonds_v

    def nn_site(self, site, d):
        """
        Index of the lattice site neighboring site in the direction d.

        Return None if there is no neighboring site in a given direction.

        Parameters
        ----------
        d: str | tuple[int, int]
            Take values in: 't', 'b', 'l', 'r', 'tl', 'bl', 'tr', 'br',
            or a tuple of (dx, dy).
        """
        if site is None:
            return None
        x, y = site
        dx, dy = self._dir[d] if isinstance(d, str) else d
        x, y = x + dx, y + dy

        if self._periodic[0] == 'o' and (x < 0 or x >= self._dims[0]):
            return None
        if self._periodic[1] == 'o' and (y < 0 or y >= self._dims[1]):
            return None
        if self._periodic[0] == 'p' and (x < 0 or x >= self._dims[0]):
            x = x % self._dims[0]
        # we don't have such option now
        # if self._periodic[1] == 'p' and (y < 0 or y >= self._dims[1]):
        #     y = y % self._dims[1]
        return Site(x, y)


    def nn_bond_type(self, bond):
        """
        For a bond corresponding to a pair of nearest-neighbor sites
        return its orientation in the 2D grid as 'lr', 'rl', 'tb', or 'bt'.
        Otherwise, return None.
        """
        s0, s1 = bond
        if self.nn_site(s0, 'r') == s1 and self.nn_site(s1, 'l') == s0:
            return 'lr'
        if self.nn_site(s0, 'b') == s1 and self.nn_site(s1, 't') == s0:
            return 'tb'
        if self.nn_site(s0, 'l') == s1 and self.nn_site(s1, 'r') == s0:
            return 'rl'
        if self.nn_site(s0, 't') == s1 and self.nn_site(s1, 'b') == s0:
            return 'bt'
        return None

    def f_ordered(self, bond):
        """ Check if bond sites appear in fermionic order. """
        s0, s1 = bond
        return s0[1] < s1[1] or (s0[1] == s1[1] and s0[0] <= s1[0])

    def site2index(self, site):
        """ Tensor index depending on site. """
        if site is None:
            return None
        x = site[0] % self._dims[0] if self._periodic[0] == 'i' else site[0]
        y = site[1] % self._dims[1] if self._periodic[1] == 'i' else site[1]
        return (x, y)


class CheckerboardLattice(SquareLattice):

    def __init__(self):
        r"""
        Geometric information about infinite checkerboard lattice.

        Checkerboard lattice is infinite lattice with 2x2 unit cell and two unique tensors.
        """
        super().__init__(dims=(2, 2), boundary='infinite')
        self._sites = (Site(0, 0), Site(0, 1))
        self._bonds_h = (Bond(Site(0, 0), Site(0, 1)), Bond(Site(0, 1), Site(0, 2)))
        self._bonds_v = (Bond(Site(0, 0), Site(1, 0)), Bond(Site(1, 0), Site(2, 0)))

    def site2index(self, site):
        """ Tensor index depending on site. """
        return (site[0] + site[1]) % 2
