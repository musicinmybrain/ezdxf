# Copyright (c) 2018-2021 Manfred Moitzi
# License: MIT License
from typing import TYPE_CHECKING, Iterator, cast, Optional, Tuple
from ezdxf.lldxf.const import DXFValueError

if TYPE_CHECKING:
    from ezdxf.eztypes import (
        DXFObject,
        Dictionary,
        Drawing,
        ObjectsSection,
        EntityDB,
    )


class ObjectCollection:
    def __init__(
        self,
        doc: "Drawing",
        dict_name: str = "ACAD_MATERIAL",
        object_type: str = "MATERIAL",
    ):
        self.doc: "Drawing" = doc
        self.object_type: str = object_type
        self.object_dict: "Dictionary" = doc.rootdict.get_required_dict(
            dict_name
        )

    def __iter__(self) -> Iterator[Tuple[str, "DXFObject"]]:
        return self.object_dict.items()

    def __len__(self) -> int:
        return len(self.object_dict)

    def __contains__(self, name: str) -> bool:
        return name in self.object_dict

    def __getitem__(self, name: str) -> "DXFObject":
        return cast("DXFObject", self.object_dict.__getitem__(name))

    def get(
        self, name: str, default: "DXFObject" = None
    ) -> Optional["DXFObject"]:
        """Get object by name.

        Args:
            name: object name as string
            default: default value

        """
        return self.object_dict.get(name, default)  # type: ignore

    def new(self, name: str) -> "DXFObject":
        """Create a new object of type `self.object_type` and store its handle
        in the object manager dictionary.

        Args:
            name: name of new object as string

        Returns:
            new object of type `self.object_type`

        Raises:
            DXFValueError: if object name already exist

        (internal API)

        """
        if name in self.object_dict:
            raise DXFValueError(
                f"{self.object_type} entry {name} already exists."
            )
        return self._new(name, dxfattribs={"name": name})

    def duplicate_entry(self, name: str, new_name: str) -> "DXFObject":
        """Returns a new table entry `new_name` as copy of `name`,
        replaces entry `new_name` if already exist.

        Raises:
             DXFValueError: `name` does not exist

        """
        entry = self.get(name)
        if entry is None:
            raise DXFValueError(f"entry '{name}' does not exist")
        entitydb = self.doc.entitydb
        if entitydb:
            new_entry = entitydb.duplicate_entity(entry)
        else:  # only for testing!
            new_entry = entry.copy()
        new_entry.dxf.name = new_name
        self.object_dict.add(name, new_entry)  # type: ignore
        return new_entry  # type: ignore

    def _new(self, name: str, dxfattribs: dict) -> "DXFObject":
        objects = self.doc.objects
        assert objects is not None

        owner = self.object_dict.dxf.handle
        dxfattribs["owner"] = owner
        obj = objects.add_dxf_object_with_reactor(
            self.object_type, dxfattribs=dxfattribs
        )
        self.object_dict.add(name, obj)
        return cast("DXFObject", obj)

    def delete(self, name: str) -> None:
        objects = self.doc.objects
        assert objects is not None

        obj = self.object_dict.get(name)
        if obj is not None:
            obj = cast("DXFObject", obj)
            self.object_dict.discard(name)
            objects.delete_entity(obj)

    def clear(self) -> None:
        """Delete all entries."""
        self.object_dict.clear()
