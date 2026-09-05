"""
flow_generator.py
Generates a skeleton process-flow diagram as draw.io XML (.drawio file).

The .drawio format is plain XML — no external libraries needed to write it,
and it imports natively into:
  - Lucidchart (Import documents → Direct file import → .drawio or .xml)
  - draw.io / diagrams.net (open directly)
  - VS Code (Draw.io Integration extension)

Shape of the flow adapts to the detected work type (T1-T5) and integration
pattern. TBD nodes get bright-yellow fill so reviewers can spot gaps.
"""

from xml.sax.saxutils import escape


def _v(field, default="TBD"):
    if field is None:
        return default
    if isinstance(field, str):
        return field
    if isinstance(field, dict) and "value" in field:
        return str(field["value"])
    return default


def _lbl(text):
    """Escape a label for use in a draw.io XML attribute. HTML <br> stays as <br>."""
    text = str(text).strip()
    return escape(text, {'"': '&quot;'})


# Draw.io shape styles
STYLES = {
    "terminal": "ellipse;whiteSpace=wrap;html=1;fillColor=#c8e6c9;strokeColor=#2e7d32;fontSize=12;fontStyle=1;",
    "trigger":  "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#e3f2fd;strokeColor=#1F3864;fontSize=12;",
    "process":  "rounded=1;whiteSpace=wrap;html=1;fillColor=#e3f2fd;strokeColor=#1F3864;fontSize=12;",
    "decision": "rhombus;whiteSpace=wrap;html=1;fillColor=#fff9c4;strokeColor=#f9a825;fontSize=12;",
    "tbd":      "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff59d;strokeColor=#f57f17;strokeWidth=2;fontSize=12;fontStyle=1;",
    "error":    "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffcdd2;strokeColor=#c62828;fontSize=12;",
}

EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;"


def _node_xml(node_id, label, style_key, x, y, w=220, h=60):
    return (
        f'        <mxCell id="{node_id}" value="{_lbl(label)}" '
        f'style="{STYLES[style_key]}" vertex="1" parent="1">\n'
        f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
        f'        </mxCell>'
    )


def _edge_xml(edge_id, source, target, label=""):
    label_attr = f' value="{_lbl(label)}"' if label else ""
    return (
        f'        <mxCell id="{edge_id}"{label_attr} '
        f'style="{EDGE_STYLE}" edge="1" parent="1" source="{source}" target="{target}">\n'
        f'          <mxGeometry relative="1" as="geometry" />\n'
        f'        </mxCell>'
    )


def generate_flow_drawio(canonical):
    """Return draw.io XML string; save as <project>.drawio."""
    src = _v(canonical.get("source", {}).get("system"))
    tgt = _v(canonical.get("target", {}).get("system"))
    src_type = _v(canonical.get("source", {}).get("interfaceType")).lower()
    tgt_type = _v(canonical.get("target", {}).get("interfaceType")).lower()
    wt_code = _v(canonical.get("integration", {}).get("workTypeCode"))
    wt_label = _v(canonical.get("integration", {}).get("workType"))
    pattern = _v(canonical.get("integration", {}).get("pattern"))
    trigger = _v(canonical.get("integration", {}).get("trigger"))
    schedule = _v(canonical.get("integration", {}).get("schedule"))
    protocol = _v(canonical.get("source", {}).get("protocol"))
    entities = ", ".join(_v(e) for e in canonical.get("entities", [])) or "TBD"
    target_table = _v(canonical.get("target", {}).get("targetTable"))
    src_auth = _v(canonical.get("security", {}).get("sourceAuth"))
    tgt_auth = _v(canonical.get("security", {}).get("targetAuth"))
    mapping_status = _v(canonical.get("mappings", {}).get("status"))
    project_name = _v(canonical.get("project", {}).get("name"), "Integration")

    # Trigger label
    if trigger != "TBD" and schedule != "TBD":
        trigger_label = f"{trigger} trigger<br>Schedule: {schedule}"
    elif trigger != "TBD":
        trigger_label = f"{trigger} trigger"
    elif "real-time" in pattern.lower() or "event" in pattern.lower():
        trigger_label = "Event received"
    else:
        trigger_label = "Trigger: TBD"

    # Extract label
    if "file" in src_type:
        extract_label = f"Pick up {entities} file from {src}<br>Protocol: {protocol}"
    elif "api" in src_type:
        extract_label = f"Call {src} API<br>Retrieve {entities}"
    elif "database" in src_type:
        extract_label = f"SELECT {entities} from {src}"
    else:
        extract_label = f"Extract {entities} from {src}"

    # Load label
    if "database" in tgt_type:
        load_label = f"Upsert into {tgt}<br>Table: {target_table}"
    elif "file" in tgt_type:
        load_label = f"Write {entities} file to {tgt}"
    elif "api" in tgt_type:
        load_label = f"POST {entities} to {tgt} API"
    else:
        load_label = f"Load to {tgt}"

    has_pagination = "api" in src_type
    has_target_auth = "api" in tgt_type

    X_MAIN = 240
    X_SIDE = 540
    Y_STEP = 90
    y = 40

    def style_for(base, *checks):
        return "tbd" if any("TBD" in str(c) for c in checks) else base

    # Main-flow nodes in order
    main = [
        ("start", "Start", "terminal"),
        ("trigger", trigger_label, style_for("trigger", trigger_label)),
        ("authsrc", f"Authenticate to {src}<br>Method: {src_auth}", style_for("process", src_auth)),
        ("extract", extract_label, style_for("process", extract_label)),
        ("validate", "Data valid?<br>Check mandatory fields", "decision"),
        ("transform", f"Transform per mapping<br>Status: {mapping_status}", style_for("process", mapping_status)),
    ]
    if has_target_auth:
        main.append(("authtgt", f"Authenticate to {tgt}<br>Method: {tgt_auth}", style_for("process", tgt_auth)))
    main.extend([
        ("load", load_label, style_for("process", load_label)),
        ("success", "Set status = Completed", "process"),
        ("notify", "Send notification<br>Recipients: TBD", "tbd"),
        ("end", "End", "terminal"),
    ])

    # Position main nodes vertically
    node_positions = {}
    for nid, label, skey in main:
        node_positions[nid] = (X_MAIN, y, skey, label)
        y += Y_STEP

    # Side branch: LogError (aligned with validate)
    err_y = node_positions["validate"][1]
    node_positions["logerror"] = (X_SIDE, err_y, "error", "Log error<br>Set status = Error")

    # Side branch: MorePages (aligned with extract) — only for API sources
    if has_pagination:
        page_y = node_positions["extract"][1]
        node_positions["morepages"] = (X_SIDE, page_y, "decision", "More pages?")

    # Edges
    edges = []

    def E(s, t, label=""):
        edges.append((f"e_{s}_{t}", s, t, label))

    E("start", "trigger")
    E("trigger", "authsrc")
    E("authsrc", "extract")
    if has_pagination:
        E("extract", "morepages")
        E("morepages", "extract", "Yes")
        E("morepages", "validate", "No")
    else:
        E("extract", "validate")
    E("validate", "transform", "Yes")
    E("validate", "logerror", "No")
    if has_target_auth:
        E("transform", "authtgt")
        E("authtgt", "load")
    else:
        E("transform", "load")
    E("load", "success")
    E("load", "logerror", "Error")
    E("success", "notify")
    E("logerror", "notify")
    E("notify", "end")

    # Assemble XML
    header = (
        '<mxfile host="app.diagrams.net" agent="DocAgent" version="24.0.0">\n'
        f'  <diagram name="Process Flow" id="flow_{wt_code}">\n'
        '    <mxGraphModel dx="1422" dy="900" grid="1" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
        'pageScale="1" pageWidth="850" pageHeight="1400" math="0" shadow="0">\n'
        '      <root>\n'
        '        <mxCell id="0" />\n'
        '        <mxCell id="1" parent="0" />\n'
    )

    title_cell = (
        f'        <mxCell id="title" value="{_lbl(project_name)} &#8212; {_lbl(wt_label)}" '
        'style="text;html=1;strokeColor=none;fillColor=none;align=center;'
        'verticalAlign=middle;whiteSpace=wrap;fontSize=16;fontStyle=1;fontColor=#1F3864;" '
        'vertex="1" parent="1">\n'
        '          <mxGeometry x="120" y="0" width="500" height="30" as="geometry" />\n'
        '        </mxCell>'
    )

    node_lines = [title_cell]
    for nid, (x, ny, skey, label) in node_positions.items():
        node_lines.append(_node_xml(nid, label, skey, x, ny))

    edge_lines = [_edge_xml(eid, s, t, lbl) for eid, s, t, lbl in edges]

    footer = (
        '\n      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
        '</mxfile>\n'
    )

    return header + "\n".join(node_lines) + "\n" + "\n".join(edge_lines) + footer
