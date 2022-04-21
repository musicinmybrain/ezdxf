# Copyright (c) 2018-2022 Manfred Moitzi
# License: MIT License
from typing import (
    List,
    Sequence,
    Tuple,
    Iterable,
    Iterator,
    TYPE_CHECKING,
    Union,
    Dict,
    TypeVar,
    Type,
)
from ezdxf.math import (
    Matrix44,
    Vec3,
    NULLVEC,
    is_planar_face,
    subdivide_face,
    normal_vector_3p,
    subdivide_ngons,
)

if TYPE_CHECKING:
    from ezdxf.eztypes import (
        Vertex,
        UCS,
        Polyface,
        Polymesh,
        GenericLayoutType,
        Mesh,
    )

T = TypeVar("T")

# (a, b): (count, balance)
# a, b = vertex indices
# count = how often this edge is used in faces as (a, b) or (b, a)
# balance = count (a, b) - count (b, a), should be 0 in "well" defined meshes,
# if balance != 0: maybe doubled faces or mixed face vertex orders
EdgeStats = Dict[Tuple[int, int], Tuple[int, int]]


def open_faces(faces: Iterable[Sequence[int]]) -> Iterator[Sequence[int]]:
    """Yields all faces with more than two vertices as open faces
    (first vertex != last vertex).
    """
    for face in faces:
        if len(face) < 3:
            continue
        if face[0] == face[-1]:
            yield face[:-1]
        else:
            yield face


def all_edges(faces: Iterable[Sequence[int]]) -> Iterator[Tuple[int, int]]:
    """Yields as face edges as int tuples."""
    for face in open_faces(faces):
        size = len(face)
        for index in range(size):
            yield face[index], face[(index + 1) % size]


def get_edge_stats(faces: Iterable[Sequence[int]]) -> EdgeStats:
    """Returns the edge statistics.

    The Edge statistic contains for each edge (a, b) the tuple (count, balance)
    where the vertex index a is always smaller than the vertex index b.

    The count is how often this edge is used in faces as (a, b) or (b, a) and
    the balance is count of (a, b) minus count of (b, a) and should be 0
    in "well" defined meshes. A balance != 0 indicates an error which may be
    double coincident faces or mixed face vertex orders.

    """
    stats: EdgeStats = {}
    for a, b in all_edges(faces):
        edge = a, b
        orientation = +1
        if a > b:
            edge = b, a
            orientation = -1
        # for all edges: count should be 2 and balance should be 0
        count, balance = stats.get(edge, (0, 0))
        stats[edge] = count + 1, balance + orientation
    return stats


class MeshStats:
    def __init__(self, mesh: "MeshBuilder"):
        self.n_vertices: int = len(mesh.vertices)
        self.n_faces: int = len(mesh.faces)
        self._edges: EdgeStats = get_edge_stats(mesh.faces)

    @property
    def n_edges(self) -> int:
        """Returns the unique edge count."""
        return len(self._edges)

    @property
    def is_watertight(self) -> bool:
        """Returns ``True`` if the mesh has a closed surface.

        This is only ``True`` for meshes with optimized vertices, see method
        :meth:`MeshBuilder.optimize_vertices`.

        """
        # https://en.wikipedia.org/wiki/Euler_characteristic
        return (self.n_vertices - self.n_edges + self.n_faces) == 2

    @property
    def is_edge_balance_broken(self) -> bool:
        """Returns ``True`` if the edge balance is broken, this indicates an
        topology error for closed surfaces (maybe mixed face vertex orientations).
        """
        return any(e[1] != 0 for e in self._edges.values())

    def total_edge_count(self) -> int:
        """Returns the total edge count of all faces, shared edges are counted
        separately for each face. In closed surfaces this count should be 2x
        the unique edge count :attr:`n_edges`.
        """
        return sum(e[0] for e in self._edges.values())

    def unique_edges(self) -> Iterable[Tuple[int, int]]:
        """Yields the unique edges of the mesh as int 2-tuples."""
        return self._edges.keys()


class MeshBuilder:
    """A simple Mesh builder. Stores a list of vertices and a faces list where
    each face is a list of indices into the vertices list.

    The :meth:`render_mesh` method, renders the mesh into a DXF MESH entity.
    The MESH entity supports ngons in AutoCAD, ngons are polygons with more
    than 4 vertices.

    Can only create new meshes.

    """

    def __init__(self):
        # vertex storage, list of (x, y, z) tuples or Vec3() objects
        self.vertices: List[Vec3] = []
        # face storage, each face is a tuple of vertex indices (v0, v1, v2, v3, ....),
        # AutoCAD supports ngons
        self.faces: List[Sequence[int]] = []

    def copy(self):
        """Returns a copy of mesh."""
        return self.from_builder(self)

    def stats(self) -> MeshStats:
        """Returns the :class:`MeshStats` for this mesh.

        .. versionadded:: 0.18

        """
        return MeshStats(self)

    def faces_as_vertices(self) -> Iterable[List[Vec3]]:
        """Yields all faces as list of vertices."""
        v = self.vertices
        for face in self.faces:
            yield [v[index] for index in face]

    def add_face(self, vertices: Iterable["Vertex"]) -> None:
        """Add a face as vertices list to the mesh. A face requires at least 3
        vertices, each vertex is a ``(x, y, z)`` tuple or
        :class:`~ezdxf.math.Vec3` object. The new vertex indices are stored as
        face in the :attr:`faces` list.

        Args:
            vertices: list of at least 3 vertices ``[(x1, y1, z1), (x2, y2, z2),
                (x3, y3, y3), ...]``

        """
        self.faces.append(self.add_vertices(vertices))

    def add_vertices(self, vertices: Iterable["Vertex"]) -> Sequence[int]:
        """Add new vertices to the mesh, each vertex is a ``(x, y, z)`` tuple
        or a :class:`~ezdxf.math.Vec3` object, returns the indices of the
        `vertices` added to the :attr:`vertices` list.

        e.g. adding 4 vertices to an empty mesh, returns the indices
        ``(0, 1, 2, 3)``, adding additional 4 vertices returns the indices
        ``(4, 5, 6, 7)``.

        Args:
            vertices: list of vertices, vertex as ``(x, y, z)`` tuple or
                :class:`~ezdxf.math.Vec3` objects

        Returns:
            tuple: indices of the `vertices` added to the :attr:`vertices` list

        """
        start_index = len(self.vertices)
        self.vertices.extend(Vec3.generate(vertices))
        return tuple(range(start_index, len(self.vertices)))

    def add_mesh(
        self,
        vertices: List[Vec3] = None,
        faces: List[Sequence[int]] = None,
        mesh=None,
    ) -> None:
        """Add another mesh to this mesh.

        A `mesh` can be a :class:`MeshBuilder`, :class:`MeshVertexMerger` or
        :class:`~ezdxf.entities.Mesh` object or requires the attributes
        :attr:`vertices` and :attr:`faces`.

        Args:
            vertices: list of vertices, a vertex is a ``(x, y, z)`` tuple or
                :class:`~ezdxf.math.Vec3` object
            faces: list of faces, a face is a list of vertex indices
            mesh: another mesh entity

        """
        if mesh is not None:
            vertices = Vec3.list(mesh.vertices)
            faces = mesh.faces

        if vertices is None:
            raise ValueError("Requires vertices or another mesh.")
        faces = faces or []
        indices = self.add_vertices(vertices)

        for face_vertices in open_faces(faces):
            self.faces.append(tuple(indices[vi] for vi in face_vertices))

    def has_none_planar_faces(self) -> bool:
        """Returns ``True`` if any face is none planar."""
        return not all(
            is_planar_face(face) for face in self.faces_as_vertices()
        )

    def render_mesh(
        self,
        layout: "GenericLayoutType",
        dxfattribs=None,
        matrix: "Matrix44" = None,
        ucs: "UCS" = None,
    ):
        """Render mesh as :class:`~ezdxf.entities.Mesh` entity into `layout`.

        Args:
            layout: :class:`~ezdxf.layouts.BaseLayout` object
            dxfattribs: dict of DXF attributes e.g. ``{'layer': 'mesh', 'color': 7}``
            matrix: transformation matrix of type :class:`~ezdxf.math.Matrix44`
            ucs: transform vertices by :class:`~ezdxf.math.UCS` to :ref:`WCS`

        """
        dxfattribs = dict(dxfattribs) if dxfattribs else {}
        vertices = self.vertices
        if matrix is not None:
            vertices = matrix.transform_vertices(vertices)
        if ucs is not None:
            vertices = ucs.points_to_wcs(vertices)  # type: ignore
        mesh = layout.add_mesh(dxfattribs=dxfattribs)
        with mesh.edit_data() as data:
            # data will be copied at setting in edit_data()
            # ignore edges and creases!
            data.vertices = list(vertices)
            data.faces = list(self.faces)  # type: ignore
        return mesh

    render = render_mesh  # TODO: 2021-02-10 - compatibility alias

    def render_normals(
        self,
        layout: "GenericLayoutType",
        length: float = 1,
        relative=True,
        dxfattribs=None,
    ):
        """Render face normals as :class:`~ezdxf.entities.Line` entities into
        `layout`, useful to check orientation of mesh faces.

        Args:
            layout: :class:`~ezdxf.layouts.BaseLayout` object
            length: visual length of normal, use length < 0 to point normals in
                opposite direction
            relative: scale length relative to face size if ``True``
            dxfattribs: dict of DXF attributes e.g. ``{'layer': 'normals', 'color': 6}``

        """
        dxfattribs = dict(dxfattribs) if dxfattribs else {}
        for face in self.faces_as_vertices():
            count = len(face)
            if count < 3:
                continue
            center = sum(face) / count
            i = 0
            n = NULLVEC
            while i <= count - 3:
                n = normal_vector_3p(face[i], face[i + 1], face[i + 2])
                if n != NULLVEC:  # not colinear vectors
                    break
                i += 1

            if relative:
                _length = (face[0] - center).magnitude * length
            else:
                _length = length
            layout.add_line(center, center + n * _length, dxfattribs=dxfattribs)

    @classmethod
    def from_mesh(cls: Type[T], other: Union["MeshBuilder", "Mesh"]) -> T:
        """Create new mesh from other mesh as class method.

        Args:
            other: `mesh` of type :class:`MeshBuilder` and inherited or DXF
                :class:`~ezdxf.entities.Mesh` entity or any object providing
                attributes :attr:`vertices`, :attr:`edges` and :attr:`faces`.

        """
        # just copy properties
        mesh = cls()
        assert isinstance(mesh, MeshBuilder)
        mesh.add_mesh(mesh=other)
        return mesh  # type: ignore

    @classmethod
    def from_polyface(cls: Type[T], other: Union["Polymesh", "Polyface"]) -> T:
        """Create new mesh from a  :class:`~ezdxf.entities.Polyface` or
        :class:`~ezdxf.entities.Polymesh` object.

        """
        if other.dxftype() != "POLYLINE":
            raise TypeError(f"Unsupported DXF type: {other.dxftype()}")

        mesh = cls()
        assert isinstance(mesh, MeshBuilder)
        if other.is_poly_face_mesh:
            _, faces = other.indexed_faces()  # type: ignore
            for face in faces:
                mesh.add_face(face.points())
        elif other.is_polygon_mesh:
            vertices = other.get_mesh_vertex_cache()  # type: ignore
            for m in range(other.dxf.m_count - 1):
                for n in range(other.dxf.n_count - 1):
                    mesh.add_face(
                        (
                            vertices[m, n],
                            vertices[m, n + 1],
                            vertices[m + 1, n + 1],
                            vertices[m + 1, n],
                        )
                    )
        else:
            raise TypeError("Not a polymesh or polyface.")
        return mesh  # type: ignore

    def render_polyface(
        self,
        layout: "GenericLayoutType",
        dxfattribs=None,
        matrix: "Matrix44" = None,
        ucs: "UCS" = None,
    ):
        """Render mesh as :class:`~ezdxf.entities.Polyface` entity into
        `layout`.

        Args:
            layout: :class:`~ezdxf.layouts.BaseLayout` object
            dxfattribs: dict of DXF attributes e.g. ``{'layer': 'mesh', 'color': 7}``
            matrix: transformation matrix of type :class:`~ezdxf.math.Matrix44`
            ucs: transform vertices by :class:`~ezdxf.math.UCS` to :ref:`WCS`

        """
        dxfattribs = dict(dxfattribs) if dxfattribs else {}
        polyface = layout.add_polyface(dxfattribs=dxfattribs)
        t = MeshTransformer.from_builder(self)
        if matrix is not None:
            t.transform(matrix)
        if ucs is not None:
            t.transform(ucs.matrix)
        polyface.append_faces(
            subdivide_ngons(t.faces_as_vertices()), dxfattribs=dxfattribs
        )
        return polyface

    def render_3dfaces(
        self,
        layout: "GenericLayoutType",
        dxfattribs=None,
        matrix: "Matrix44" = None,
        ucs: "UCS" = None,
    ):
        """Render mesh as :class:`~ezdxf.entities.Face3d` entities into
        `layout`.

        Args:
            layout: :class:`~ezdxf.layouts.BaseLayout` object
            dxfattribs: dict of DXF attributes e.g. ``{'layer': 'mesh', 'color': 7}``
            matrix: transformation matrix of type :class:`~ezdxf.math.Matrix44`
            ucs: transform vertices by :class:`~ezdxf.math.UCS` to :ref:`WCS`

        """
        dxfattribs = dict(dxfattribs) if dxfattribs else {}
        t = MeshTransformer.from_builder(self)
        if matrix is not None:
            t.transform(matrix)
        if ucs is not None:
            t.transform(ucs.matrix)
        for face in subdivide_ngons(t.faces_as_vertices()):
            layout.add_3dface(face, dxfattribs=dxfattribs)

    @classmethod
    def from_builder(cls: Type[T], other: "MeshBuilder") -> T:
        """Create new mesh from other mesh builder, faster than
        :meth:`from_mesh` but supports only :class:`MeshBuilder` and inherited
        classes.

        """
        # just copy properties
        mesh = cls()
        assert isinstance(mesh, MeshBuilder)
        mesh.vertices = list(other.vertices)
        mesh.faces = list(other.faces)
        return mesh  # type: ignore

    def merge_coplanar_faces(self, passes: int = 1) -> "MeshTransformer":
        """Returns a new :class:`MeshBuilder` object with merged adjacent
        coplanar faces.

        The faces have to share at least two vertices and have to have the
        same clockwise or counter-clockwise vertex order.

        The current implementation is not very capable!

        .. versionadded:: 0.18

        """
        mesh = self
        for _ in range(passes):
            mesh = _merge_adjacent_coplanar_faces(mesh.vertices, mesh.faces)
        return MeshTransformer.from_builder(mesh)

    def subdivide(self, level: int = 1, quads=True) -> "MeshTransformer":
        """Returns a new :class:`MeshTransformer` object with subdivided faces
        and edges.

        Args:
             level: subdivide levels from 1 to max of 5
             quads: create quad faces if ``True`` else create triangles
        """
        mesh = self
        level = min(int(level), 5)
        while level > 0:
            mesh = _subdivide(mesh, quads)  # type: ignore
            level -= 1
        return MeshTransformer.from_builder(mesh)

    def optimize_vertices(self, precision: int = 6) -> "MeshTransformer":
        """Returns a new mesh with optimized vertices. Coincident vertices are
        merged together and all faces are open faces (first vertex != last
        vertex).

        .. versionadded:: 0.18

        """
        m1 = MeshVertexMerger(precision=precision)
        m1.add_mesh(mesh=self)
        m2 = MeshTransformer()
        # no need for copying
        m2.vertices = m1.vertices
        m2.faces = m1.faces
        return m2


class MeshTransformer(MeshBuilder):
    """A mesh builder with inplace transformation support."""

    def transform(self, matrix: "Matrix44"):
        """Transform mesh inplace by applying the transformation `matrix`.

        Args:
            matrix: 4x4 transformation matrix as :class:`~ezdxf.math.Matrix44`
                object

        """
        self.vertices = list(matrix.transform_vertices(self.vertices))
        return self

    def translate(self, dx: float = 0, dy: float = 0, dz: float = 0):
        """Translate mesh inplace.

        Args:
            dx: translation in x-axis
            dy: translation in y-axis
            dz: translation in z-axis

        """
        if isinstance(dx, (float, int)):
            t = Vec3(dx, dy, dz)
        else:
            t = Vec3(dx)
        self.vertices = [t + v for v in self.vertices]
        return self

    def scale(self, sx: float = 1, sy: float = 1, sz: float = 1):
        """Scale mesh inplace.

        Args:
            sx: scale factor for x-axis
            sy: scale factor for y-axis
            sz: scale factor for z-axis

        """
        self.vertices = [
            Vec3(x * sx, y * sy, z * sz) for x, y, z in self.vertices
        ]
        return self

    def scale_uniform(self, s: float):
        """Scale mesh uniform inplace.

        Args:
            s: scale factor for x-, y- and z-axis

        """
        self.vertices = [v * s for v in self.vertices]
        return self

    def rotate_x(self, angle: float):
        """Rotate mesh around x-axis about `angle` inplace.

        Args:
            angle: rotation angle in radians

        """
        self.vertices = list(
            Matrix44.x_rotate(angle).transform_vertices(self.vertices)
        )
        return self

    def rotate_y(self, angle: float):
        """Rotate mesh around y-axis about `angle` inplace.

        Args:
            angle: rotation angle in radians

        """
        self.vertices = list(
            Matrix44.y_rotate(angle).transform_vertices(self.vertices)
        )
        return self

    def rotate_z(self, angle: float):
        """Rotate mesh around z-axis about `angle` inplace.

        Args:
            angle: rotation angle in radians

        """
        self.vertices = list(
            Matrix44.z_rotate(angle).transform_vertices(self.vertices)
        )
        return self

    def rotate_axis(self, axis: "Vertex", angle: float):
        """Rotate mesh around an arbitrary axis located in the origin (0, 0, 0)
        about `angle`.

        Args:
            axis: rotation axis as Vec3
            angle: rotation angle in radians

        """
        self.vertices = list(
            Matrix44.axis_rotate(axis, angle).transform_vertices(self.vertices)
        )
        return self


def _subdivide(mesh, quads=True) -> "MeshVertexMerger":
    """Returns a new :class:`MeshVertexMerger` object with subdivided faces
    and edges.

    Args:
         quads: create quad faces if ``True`` else create triangles

    """
    new_mesh = MeshVertexMerger()
    for vertices in mesh.faces_as_vertices():
        if len(vertices) < 3:
            continue
        for face in subdivide_face(vertices, quads):
            new_mesh.add_face(face)
    return new_mesh


class MeshVertexMerger(MeshBuilder):
    """Subclass of :class:`MeshBuilder`

    Mesh with unique vertices and no doublets, but needs extra memory for
    bookkeeping.

    :class:`MeshVertexMerger` creates a key for every vertex by rounding its
    components by the Python :func:`round` function and a given `precision`
    value. Each vertex with the same key gets the same vertex index, which is
    the index of first vertex with this key, so all vertices with the same key
    will be located at the location of this first vertex. If you want an average
    location of and for all vertices with the same key look at the
    :class:`MeshAverageVertexMerger` class.

    Args:
        precision: floating point precision for vertex rounding

    """

    # can not support vertex transformation
    def __init__(self, precision: int = 6):
        """
        Args:
            precision: floating point precision for vertex rounding

        """
        super().__init__()
        self.ledger: Dict[Vec3, int] = {}
        self.precision: int = precision

    def add_vertices(self, vertices: Iterable["Vertex"]) -> Sequence[int]:
        """Add new `vertices` only, if no vertex with identical (x, y, z)
        coordinates already exist, else the index of the existing vertex is
        returned as index of the added vertices.

        Args:
            vertices: list of vertices, vertex as (x, y, z) tuple or
                :class:`~ezdxf.math.Vec3` objects

        Returns:
            indices of the added `vertices`

        """
        indices = []
        precision = self.precision
        for vertex in Vec3.generate(vertices):
            key = vertex.round(precision)
            try:
                indices.append(self.ledger[key])
            except KeyError:
                index = len(self.vertices)
                self.vertices.append(vertex)
                self.ledger[key] = index
                indices.append(index)
        return tuple(indices)

    def index(self, vertex: "Vertex") -> int:
        """Get index of `vertex`, raise :class:`KeyError` if not found.

        Args:
            vertex: ``(x, y, z)`` tuple or :class:`~ezdxf.math.Vec3` object

        (internal API)
        """
        try:
            return self.ledger[Vec3(vertex).round(self.precision)]
        except KeyError:
            raise IndexError(f"Vertex {str(vertex)} not found.")

    @classmethod
    def from_builder(cls, other: "MeshBuilder") -> "MeshVertexMerger":
        """Create new mesh from other mesh builder."""
        # rebuild from scratch to create a valid ledger
        return cls.from_mesh(other)


class MeshAverageVertexMerger(MeshBuilder):
    """Subclass of :class:`MeshBuilder`

    Mesh with unique vertices and no doublets, but needs extra memory for
    bookkeeping and runtime for calculation of average vertex location.

    :class:`MeshAverageVertexMerger` creates a key for every vertex by rounding
    its components by the Python :func:`round` function and a given `precision`
    value. Each vertex with the same key gets the same vertex index, which is the
    index of first vertex with this key, the difference to the
    :class:`MeshVertexMerger` class is the calculation of the average location
    for all vertices with the same key, this needs extra memory to keep track of
    the count of vertices for each key and extra runtime for updating the vertex
    location each time a vertex with an existing key is added.

    Args:
        precision: floating point precision for vertex rounding

    """

    # can not support vertex transformation
    def __init__(self, precision: int = 6):
        super().__init__()
        self.ledger: Dict[
            Vec3, Tuple[int, int]
        ] = {}  # each key points to a tuple (vertex index, vertex count)
        self.precision: int = precision

    def add_vertices(self, vertices: Iterable["Vertex"]) -> Sequence[int]:
        """Add new `vertices` only, if no vertex with identical ``(x, y, z)``
        coordinates already exist, else the index of the existing vertex is
        returned as index of the added vertices.

        Args:
            vertices: list of vertices, vertex as ``(x, y, z)`` tuple or
            :class:`~ezdxf.math.Vec3` objects

        Returns:
            tuple: indices of the `vertices` added to the
            :attr:`~MeshBuilder.vertices` list

        """
        indices = []
        precision = self.precision
        for vertex in Vec3.generate(vertices):
            key = vertex.round(precision)
            try:
                index, count = self.ledger[key]
            except KeyError:  # new key
                index = len(self.vertices)
                self.vertices.append(vertex)
                self.ledger[key] = (index, 1)
            else:  # update key entry
                # calculate new average location
                average = (self.vertices[index] * count) + vertex
                count += 1
                # update vertex location
                self.vertices[index] = average / count
                # update ledger
                self.ledger[key] = (index, count)
            indices.append(index)
        return tuple(indices)

    def index(self, vertex: "Vertex") -> int:
        """Get index of `vertex`, raise :class:`KeyError` if not found.

        Args:
            vertex: ``(x, y, z)`` tuple or :class:`~ezdxf.math.Vec3` object

        (internal API)
        """
        try:
            return self.ledger[Vec3(vertex).round(self.precision)][0]
        except KeyError:
            raise IndexError(f"Vertex {str(vertex)} not found.")

    @classmethod
    def from_builder(cls, other: "MeshBuilder") -> "MeshAverageVertexMerger":
        """Create new mesh from other mesh builder."""
        # rebuild from scratch to create a valid ledger
        return cls.from_mesh(other)


class _XFace:
    __slots__ = ("fingerprint", "indices", "_orientation")

    def __init__(self, indices: Sequence[int]):
        self.fingerprint: int = hash(indices)
        self.indices: Sequence[int] = indices
        self._orientation: Vec3 = VEC3_SENTINEL

    def orientation(self, vertices: Sequence[Vec3], precision: int = 4) -> Vec3:
        if self._orientation is VEC3_SENTINEL:
            orientation = NULLVEC
            v0, v1, *v = [vertices[i] for i in self.indices]
            for v2 in v:
                try:
                    orientation = normal_vector_3p(v0, v1, v2).round(precision)
                    break
                except ZeroDivisionError:
                    continue
            self._orientation = orientation
        return self._orientation


def _merge_adjacent_coplanar_faces(
    vertices: List[Vec3], faces: List[Sequence[int]], precision: int = 4
) -> MeshVertexMerger:
    oriented_faces: dict[Vec3, List[_XFace]] = {}
    extended_faces: List[_XFace] = []
    for face in faces:
        if len(face) < 3:
            raise ValueError("found invalid face count < 3")
        xface = _XFace(face)
        extended_faces.append(xface)
        oriented_faces.setdefault(
            xface.orientation(vertices, precision), []
        ).append(xface)

    mesh = MeshVertexMerger()
    done = set()
    for xface in extended_faces:
        if xface.fingerprint in done:
            continue
        done.add(xface.fingerprint)
        face = xface.indices
        orientation = xface.orientation(vertices, precision)
        parallel_faces = oriented_faces[orientation]
        face_set = set(face)
        for parallel_face in parallel_faces:
            if parallel_face.fingerprint in done:
                continue
            common_vertices = face_set.intersection(set(parallel_face.indices))
            # connection by at least 2 vertices required:
            if len(common_vertices) > 1:
                if len(common_vertices) == len(parallel_face.indices):
                    face = merge_full_patch(face, parallel_face.indices)
                else:
                    try:
                        face = merge_connected_paths(
                            face, parallel_face.indices
                        )
                    except (NodeMergingError, DegeneratedPathError):
                        continue
                done.add(parallel_face.fingerprint)
                face_set = set(face)
        v0 = list(remove_colinear_face_vertices([vertices[i] for i in face]))
        mesh.add_face(v0)
    return mesh


VEC3_SENTINEL = Vec3(0, 0, 0)


def remove_colinear_face_vertices(vertices: Sequence[Vec3]) -> Iterator[Vec3]:
    def get_direction(v1: Vec3, v2: Vec3):
        return (v2 - v1).normalize()

    if len(vertices) < 3:
        yield from vertices
        return

    # remove duplicated vertices
    _vertices: List[Vec3] = [vertices[0]]
    for v in vertices[1:]:
        if not v.isclose(_vertices[-1]):
            _vertices.append(v)

    if len(_vertices) < 3:
        if len(_vertices) == 1:
            _vertices.append(_vertices[0])
        yield from _vertices
        return

    start = _vertices[0]
    prev_vertex = VEC3_SENTINEL
    current_direction = VEC3_SENTINEL
    start_index = 0

    # find start direction
    yield start
    while current_direction is VEC3_SENTINEL:
        start_index += 1
        try:
            prev_vertex = vertices[start_index]
        except IndexError:
            yield prev_vertex
            return
        current_direction = get_direction(start, prev_vertex)

    yielded_anything = False
    _vertices.append(start)
    for vertex in _vertices[start_index:]:
        try:
            if get_direction(start, vertex).isclose(current_direction):
                prev_vertex = vertex
                continue
        except ZeroDivisionError:
            continue
        yield prev_vertex
        yielded_anything = True
        start = prev_vertex
        current_direction = get_direction(start, vertex)
        prev_vertex = vertex

    if not yielded_anything:
        yield _vertices[-2]  # last vertex


class NodeMergingError(Exception):
    pass


class DegeneratedPathError(Exception):
    pass


def merge_connected_paths(
    p1: Sequence[int], p2: Sequence[int]
) -> Sequence[int]:
    def build_nodes(p: Sequence[int]):
        nodes = {e1: e2 for e1, e2 in zip(p, p[1:])}
        nodes[p[-1]] = p[0]
        return nodes

    current_path = build_nodes(p1)
    other_path = build_nodes(p2)
    current_node = p1[0]
    finish = p1[0]
    connected_path = [current_node]
    while True:
        try:
            next_node = current_path[current_node]
        except KeyError:
            raise NodeMergingError
        if next_node in other_path:
            current_path, other_path = other_path, current_path
        if next_node == finish:
            break
        current_node = next_node
        if current_node in connected_path:
            # node duplication is an error, e.g. two path are only connected
            # by one node:
            raise NodeMergingError
        connected_path.append(current_node)

    if len(connected_path) < 3:
        raise DegeneratedPathError
    return connected_path


def merge_full_patch(path: Sequence[int], patch: Sequence[int]):
    count = len(path)
    new_path = []
    for pos, node in enumerate(path):
        prev = path[pos - 1]
        succ = path[(pos + 1) % count]
        if prev in patch and succ in patch:
            continue
        new_path.append(node)
    return new_path
