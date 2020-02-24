# Copyright (c) 2020, Manfred Moitzi
# License: MIT License
from typing import Iterable, cast, BinaryIO, Tuple, Dict
from io import StringIO
from ezdxf.lldxf.const import DXFStructureError
from ezdxf.lldxf.extendedtags import ExtendedTags, DXFTag
from ezdxf.lldxf.tagwriter import TagWriter
from ezdxf.lldxf.tagger import tag_compiler
from ezdxf.lldxf import fileindex

from ezdxf.entities import DXFGraphic
from ezdxf.entities.factory import EntityFactory
from ezdxf.entities.dxfgfx import entity_linker
from ezdxf.tools.codepage import toencoding

__all__ = ['opendxf', 'single_pass_modelspace']

SUPPORTED_DXF_TYPES = {
    'ARC', 'LINE', 'CIRCLE', 'ELLIPSE', 'POINT', 'LWPOLYLINE', 'SPLINE', '3DFACE', 'SOLID', 'TRACE',
    'POLYLINE', 'VERTEX', 'SEQEND', 'MESH', 'TEXT', 'MTEXT', 'HATCH', 'INSERT', 'ATTRIB', 'ATTDEF',
}


class IterDXF:
    """ Iterator for DXF entities stored in the modelspace.

    Args:
         name: filename, has to be a seekable file.

    Raises:
        DXFStructureError: Invalid or incomplete DXF file

    """

    def __init__(self, name: str):
        self.structure, self.sections = self._load_index(name)
        self.file: BinaryIO = open(name, mode='rb')
        if 'ENTITIES' not in self.sections:
            raise DXFStructureError('ENTITIES section not found.')
        if self.structure.version > 'AC1009' and 'OBJECTS' not in self.sections:
            raise DXFStructureError('OBJECTS section not found.')

    def _load_index(self, name: str) -> Tuple[fileindex.FileStructure, Dict[str, int]]:
        structure = fileindex.load(name)
        sections: Dict[str, int] = dict()
        new_index = []
        for e in structure.index:
            if e.code == 0:
                new_index.append(e)
            elif e.code == 2:
                sections[e.value] = len(new_index) - 1
            # remove all other tags like handles (code == 5)
        structure.index = new_index
        return structure, sections

    @property
    def encoding(self):
        return self.structure.encoding

    @property
    def dxfversion(self):
        return self.structure.version

    def export(self, name: str) -> 'IterDXFWriter':
        """
        Returns a companion object to export parts from the source DXF file into another DXF file, the new file will
        have the same HEADER, CLASSES, TABLES, BLOCKS and OBJECTS sections, which guarantees all necessary dependencies
        are present in the new file.

        Args:
            name: filename, no special requirements

        """
        doc = IterDXFWriter(name, self)
        # Copy everything from start of source DXF until the first entity
        # of the ENTITIES section to the new DXF.
        location = self.structure.index[self.sections['ENTITIES'] + 1].location
        self.file.seek(0)
        data = self.file.read(location)
        doc.write_data(data)
        return doc

    def copy_objects_section(self, f: BinaryIO) -> None:
        start_index = self.sections['OBJECTS']
        try:
            end_index = self.structure.get(0, 'ENDSEC', start_index)
        except ValueError:
            raise DXFStructureError(f'ENDSEC of OBJECTS section not found.')

        start_location = self.structure.index[start_index].location
        end_location = self.structure.index[end_index + 1].location
        count = end_location - start_location
        self.file.seek(start_location)
        data = self.file.read(count)
        f.write(data)

    def modelspace(self) -> Iterable[DXFGraphic]:
        """

        Returns an iterator for all supported DXF entities in the modelspace. These entities are regular
        :class:`~ezdxf.entities.DXFGraphic` objects but without a valid document assigned. It is **not**
        possible to add these entities to other `ezdxf` documents.

        It is only possible to recreate the objects by factory functions base on attributes of the source entity.
        For MESH, POLYMESH and POLYFACE it is possible to use the :class:`~ezdxf.render.MeshTransformer` class to
        render (recreate) this objects as new entities in another document.

        """
        linked_entity = entity_linker()
        queued = None
        for entity in self.load_entities(self.sections['ENTITIES'] + 1):
            if not linked_entity(entity) and entity.dxf.paperspace == 0:
                if queued:  # queue one entity for collecting linked entities (VERTEX, ATTRIB)
                    yield queued
                queued = entity
        if queued:
            yield queued

    def load_entities(self, start: int) -> Iterable[DXFGraphic]:
        def to_str(data: bytes) -> str:
            return data.decode(self.encoding).replace('\r\n', '\n')

        factory = EntityFactory()
        index = start
        entry = self.structure.index[index]
        self.file.seek(entry.location)
        while entry.value != 'ENDSEC':
            index += 1
            next_entry = self.structure.index[index]
            size = next_entry.location - entry.location
            data = self.file.read(size)
            if entry.value in SUPPORTED_DXF_TYPES:
                xtags = ExtendedTags.from_text(to_str(data))
                yield factory.entity(xtags)
            entry = next_entry

    def close(self):
        """ Safe closing source DXF file. """
        self.file.close()


class IterDXFWriter:
    def __init__(self, name: str, loader: IterDXF):
        self.name = str(name)
        self.file: BinaryIO = open(name, mode='wb')
        self.text = StringIO()
        self.entity_writer = TagWriter(self.text, loader.dxfversion)
        self.loader = loader

    def write_data(self, data: bytes):
        self.file.write(data)

    def write(self, entity: DXFGraphic):
        """ Write a DXF entity from the source DXF file to the export file.

        Don't write entities from different documents than the source DXF file, dependencies and resources will not
        match, maybe it will work once, but not in a reliable way for different DXF documents.

        """
        # remove all possible dependencies
        entity.xdata = None
        entity.appdata = None
        entity.extension_dict = None
        entity.reactors = None
        # reset text stream
        self.text.seek(0)
        self.text.truncate()

        entity.export_dxf(self.entity_writer)
        if entity.dxftype() == 'POLYLINE':
            polyline = cast('Polyline', entity)
            for vertex in polyline.vertices:
                vertex.export_dxf(self.entity_writer)
            polyline.seqend.export_dxf(self.entity_writer)
        elif entity.dxftype() == 'INSERT':
            insert = cast('Insert', entity)
            if insert.attribs_follow:
                for attrib in insert.attribs:
                    attrib.export_dxf(self.entity_writer)
                insert.seqend.export_dxf(self.entity_writer)
        data = self.text.getvalue().encode(self.loader.encoding)
        self.file.write(data)

    def close(self):
        """
        Safe closing of exported DXF file. Copying of OBJECTS section happens only at closing the file,
        without closing the new DXF file is invalid.
        """
        self.file.write(b'  0\r\nENDSEC\r\n')  # for ENTITIES section
        if self.loader.dxfversion > 'AC1009':
            self.loader.copy_objects_section(self.file)
        self.file.write(b'  0\r\nEOF\r\n')
        self.file.close()


def opendxf(filename: str) -> IterDXF:
    """ Open DXF file for iterating, be sure to open valid DXF files, no DXF structure checks will be applied.

    Args:
        filename: DXF filename of a seekable file.

    """
    return IterDXF(filename)


def single_pass_modelspace(stream: BinaryIO) -> Iterable[DXFGraphic]:
    """
    Iterate over all modelspace entities as :class:`DXFGraphic` objects in one single pass.
    The DXF stream requires a HEADER section!

    Only useful if the binary stream is not seekable else :func:`iterdxf.opendxf` is slightly faster.

    Args:
        stream: (not seekable) binary stream

    """
    fetch_header_var = False
    encoding = 'cp1252'
    version = 'AC1009'

    # requires a HEADER section
    for code, value in binary_tagger(stream):
        if code == 0 and value == b'ENDSEC':
            break
        if code == 9 and value == b'$DWGCODEPAGE':
            fetch_header_var = 'ENCODING'
        elif code == 9 and value == b'$ACADVERSION':
            fetch_header_var = 'VERSION'
        elif fetch_header_var:
            if fetch_header_var == 'ENCODING':
                encoding = toencoding(value.decode())
            elif fetch_header_var == 'VERSION':
                version = value.decode()
            fetch_header_var = False

    prev_code: int = -1
    prev_value: str = ''
    structure = None  # the actual structure tag: 'SECTION', 'LINE', ...
    queued = False

    tags = []
    factory = EntityFactory()
    linked_entity = entity_linker()

    def build_entity():
        xtags = ExtendedTags(tags)
        return factory.entity(xtags)

    entities = False
    for tag in tag_compiler(binary_tagger(stream, encoding)):
        code = tag.code
        value = tag.value
        if entities:
            if code == 0 and value == 'ENDSEC':
                if queued:
                    yield queued
                return
            if code == 0:
                if len(tags) and structure in SUPPORTED_DXF_TYPES:
                    entity = build_entity()
                    if not linked_entity(entity) and entity.dxf.paperspace == 0:
                        if queued:  # queue one entity for collecting linked entities (VERTEX, ATTRIB)
                            yield queued
                        queued = entity
                structure = value
                tags = [tag]
            else:
                tags.append(tag)
            continue  # nothing else matters
        elif code == 0:
            structure = value
        elif code == 2 and prev_code == 0 and prev_value == 'SECTION':
            entities = (value == 'ENTITIES')
            if entities and version > 'AC1009':
                encoding = 'utf-8'

        prev_code = code
        prev_value = value
    stream.close()


def binary_tagger(file: BinaryIO, encoding=None) -> DXFTag:
    def load_tag() -> DXFTag:
        try:
            code = int(file.readline())
        except ValueError:
            raise DXFStructureError(f'Invalid group code')

        if code < 0 or code > 1071:
            raise DXFStructureError(f'Invalid group code {code}')
        value = file.readline().rstrip(b'\r\n')

        if encoding:
            return DXFTag(code, value.decode(encoding))
        else:
            return DXFTag(code, value)

    while True:
        try:
            yield load_tag()
        except IOError:
            return
