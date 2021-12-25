#  Copyright (c) 2021, Manfred Moitzi
#  License: MIT License

import pathlib
import logging

import ezdxf
from ezdxf import colors
from ezdxf.gfxattribs import GfxAttribs
from ezdxf.math import Vec2, UCS, NULLVEC
from ezdxf.render.mleader import (
    ConnectionSide,
    VerticalConnection,
    HorizontalConnection,
    TextAlignment,
)

# ========================================
# Setup logging
# ========================================
logging.basicConfig(level="WARNING")

# ========================================
# Setup your preferred output directory
# ========================================
OUTDIR = pathlib.Path("~/Desktop/Outbox").expanduser()
if not OUTDIR.exists():
    OUTDIR = pathlib.Path()

DXFVERSION = "R2013"


def simple_mtext_content_horizontal(name: str):
    doc = ezdxf.new(DXFVERSION, setup=True)
    msp = doc.modelspace()
    ml_builder = msp.add_multileader_mtext("Standard")
    ml_builder.set_content("Line1\nLine2", style="OpenSans")

    # Construction plane of the entity is defined by an render UCS.
    # The default render UCS is the WCS.
    # The leader lines vertices are expected in render UCS coordinates, which
    # means relative to the UCS origin!
    # This example shows the simplest way UCS==WCS!
    ml_builder.add_leader_line(ConnectionSide.right, [Vec2(40, 15)])
    ml_builder.add_leader_line(ConnectionSide.right, [Vec2(40, -15)])
    ml_builder.add_leader_line(ConnectionSide.left, [Vec2(-20, -15)])

    # The insert point (in UCS coordinates= is the alignment point for MTEXT
    # content and the insert location for BLOCK content:
    ml_builder.build(insert=Vec2(5, 0))

    doc.set_modelspace_vport(60, center=(10, 5))
    doc.saveas(OUTDIR / f"{name}_{DXFVERSION}.dxf")


def all_mtext_content_horizontal(name: str):
    doc = ezdxf.new(DXFVERSION, setup=True)
    msp = doc.modelspace()
    attribs = GfxAttribs(color=colors.RED)
    for direction in range(9):
        for ax, alignment in enumerate(
            [
                TextAlignment.left,
                TextAlignment.center,
                TextAlignment.right,
            ]
        ):
            ml_builder = msp.add_multileader_mtext("Standard")
            dir_enum = HorizontalConnection(direction)
            ml_builder.set_connection_types(
                left=dir_enum,
                right=dir_enum,
            )

            ml_builder.set_content(
                f"{dir_enum.name}\n{dir_enum.name}\n{dir_enum.name}",
                alignment=alignment,
                style="OpenSans",
            )
            width = len(dir_enum.name) * 2.5
            x0 = -30
            x1 = 40 + width
            y0 = -15
            y1 = 20

            ml_builder.add_leader_line(ConnectionSide.right, [Vec2(x1, y1)])
            ml_builder.add_leader_line(ConnectionSide.right, [Vec2(x1, y0)])
            ml_builder.add_leader_line(ConnectionSide.left, [Vec2(x0, y0)])
            ml_builder.add_leader_line(ConnectionSide.left, [Vec2(x0, y1)])
            x = 5
            if alignment == TextAlignment.center:
                x += width / 2
            elif alignment == TextAlignment.right:
                x += width
            ucs = UCS(origin=(ax * 250, direction * 50))
            insert = Vec2(x, y1/2)
            ml_builder.build(insert=insert, ucs=ucs)
            e = msp.add_lwpolyline(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                close=True,
                dxfattribs=attribs,
            )
            e.transform(ucs.matrix)
            e = msp.add_circle(insert, radius=0.5, dxfattribs=attribs)
            e.transform(ucs.matrix)

    height = 600
    doc.set_modelspace_vport(height, center=(200, height / 2))
    doc.saveas(OUTDIR / f"{name}_{DXFVERSION}.dxf")


def simple_mtext_content_vertical(name: str):
    doc = ezdxf.new(DXFVERSION, setup=True)
    msp = doc.modelspace()
    ml_builder = msp.add_multileader_mtext("Standard")
    ml_builder.set_content("Line1\nLine2", style="OpenSans")

    # Construction plane of the entity is defined by an render UCS.
    # The default render UCS is the WCS.
    # The leader lines vertices are expected in render UCS coordinates, which
    # means relative to the UCS origin!
    # This example shows the simplest way UCS==WCS!
    ml_builder.set_connection_types(
        top=VerticalConnection.center_overline,
        bottom=VerticalConnection.center_overline,
    )
    ml_builder.add_leader_line(ConnectionSide.top, [Vec2(15, 40)])
    ml_builder.add_leader_line(ConnectionSide.bottom, [Vec2(15, -40)])

    # The insert point (in UCS coordinates= is the alignment point for MTEXT
    # content and the insert location for BLOCK content:
    ml_builder.build(insert=Vec2(5, 0))
    msp.add_circle(
        ml_builder.multileader.context.base_point,
        radius=0.5,
        dxfattribs=GfxAttribs(color=colors.RED),
    )
    doc.set_modelspace_vport(60, center=(10, 5))
    doc.saveas(OUTDIR / f"{name}_{DXFVERSION}.dxf")


def quick_mtext_horizontal(name: str):
    doc = ezdxf.new(DXFVERSION, setup=True)
    mleaderstyle = doc.mleader_styles.duplicate_entry("Standard", "EZDXF")
    mleaderstyle.set_mtext_style("OpenSans")  # type: ignore
    msp = doc.modelspace()
    target_point = Vec2(40, 15)
    msp.add_circle(
        target_point, radius=0.5, dxfattribs=GfxAttribs(color=colors.RED)
    )

    for angle in [45, 135, 225, -45]:
        ml_builder = msp.add_multileader_mtext("EZDXF")
        ml_builder.quick_leader(
            "Line1\nLine2",
            target=target_point,
            segment1=Vec2.from_deg_angle(angle, 14),
        )

    doc.set_modelspace_vport(60, center=(10, 5))
    doc.saveas(OUTDIR / f"{name}_{DXFVERSION}.dxf")


def quick_mtext_vertical(name: str):
    doc = ezdxf.new(DXFVERSION, setup=True)
    mleaderstyle = doc.mleader_styles.duplicate_entry("Standard", "EZDXF")
    mleaderstyle.set_mtext_style("OpenSans")  # type: ignore
    msp = doc.modelspace()
    target_point = Vec2(40, 15)
    msp.add_circle(
        target_point, radius=0.5, dxfattribs=GfxAttribs(color=colors.RED)
    )

    for angle in [45, 135, 225, -45]:
        ml_builder = msp.add_multileader_mtext("EZDXF")
        ml_builder.quick_leader(
            "Line1\nLine2",
            target=target_point,
            segment1=Vec2.from_deg_angle(angle, 14),
            connection_type=VerticalConnection.center_overline,
        )

    doc.set_modelspace_vport(60, center=(10, 5))
    doc.saveas(OUTDIR / f"{name}_{DXFVERSION}.dxf")


if __name__ == "__main__":
    quick_mtext_horizontal("mleader_quick_mtext_horizontal")
    quick_mtext_vertical("mleader_quick_mtext_vertical")
    simple_mtext_content_horizontal("mleader_simple_mtext_horizontal")
    simple_mtext_content_vertical("mleader_simple_mtext_vertical")
    all_mtext_content_horizontal("mleader_all_mtext_horizontal")
