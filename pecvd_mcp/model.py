from __future__ import annotations

import csv
import html
import importlib.resources
import json
import math
import re
from pathlib import Path

VARIANTS = ("baseline", "center_open", "edge_open")


def baseline() -> dict:
    return json.loads(importlib.resources.files("pecvd_mcp").joinpath("baseline.json").read_text(encoding="utf-8"))


def conversions() -> dict:
    b = baseline()
    p, a = b["reported"], b["assumed_for_unit_conversion_only"]
    mole_per_sccm = 1e-6 / 60 * a["sccm_standard_pressure_Pa"] / (8.314462618 * a["sccm_standard_temperature_K"])
    total = p["SiH4_sccm"] + p["NH3_sccm"]
    x_si = p["SiH4_sccm"] / total
    mw = x_si * a["SiH4_molar_mass_kg_per_mol"] + (1-x_si) * a["NH3_molar_mass_kg_per_mol"]
    return {
        "pressure_Pa": p["outlet_pressure_Torr"] * 133.32236842105263,
        "SiH4_mole_fraction": x_si,
        "SiH4_mass_fraction": x_si * a["SiH4_molar_mass_kg_per_mol"] / mw,
        "mixture_molecular_weight_kg_per_kmol": mw * 1000,
        "total_mass_flow_kg_s": total * mole_per_sccm * mw,
        "standard_state_assumed_not_reported": a,
    }


def positive(value: float, name: str, allow_zero: bool = False) -> float:
    value = float(value)
    if not math.isfinite(value) or (value < 0 if allow_zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return value


def project_path(root: Path, project_id: str, must_exist: bool = True) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", project_id):
        raise ValueError("Project ID: 1-64 ASCII letters, digits, underscore or hyphen")
    root = root.resolve()
    path = (root / project_id).resolve()
    if path.parent != root:
        raise ValueError("Project path escapes workspace")
    if must_exist and not (path / "project.json").is_file():
        raise ValueError("Create the project first")
    return path


def local_file(project: Path, relative: str, suffixes: tuple[str, ...]) -> Path:
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or not any(path.name.endswith(s) for s in suffixes):
        raise ValueError("Only permitted files within the project directory may be used")
    if not path.is_file() or path.stat().st_size > 200 * 1024 * 1024:
        raise ValueError("File missing or larger than 200 MiB")
    return path


def generate_mesh(path: Path, variant: str = "baseline", nr: int = 132, nz: int = 24) -> dict:
    """2D Fluent ASCII face mesh. x=axial z, y=radius; SI meters.

    This is a connection-test gap model, not the paper's plenum/porous model.
    Each oriented edge has c0 to its left; its outward normal is (dy,-dx).
    """
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    if isinstance(nr, bool) or isinstance(nz, bool) or not isinstance(nr, int) or not isinstance(nz, int):
        raise ValueError("Grid counts must be integers")
    if not (22 <= nr <= 528 and nr % 11 == 0 and 4 <= nz <= 192 and nr*nz <= 50000):
        raise ValueError("nr: multiple of 11, 22-528; nz: 4-192; maximum 50000 cells")
    rmax, height = 0.165, 0.015
    node = lambda j, i: j*(nr+1)+i+1
    cell = lambda j, i: j*nr+i+1
    coords = [(height*j/nz, rmax*i/nr) for j in range(nz+1) for i in range(nr+1)]
    edge_map = {}
    for j in range(nz):
        for i in range(nr):
            vertices = [node(j,i),node(j+1,i),node(j+1,i+1),node(j,i+1)]
            for n1,n2 in zip(vertices,vertices[1:]+vertices[:1]):
                key = tuple(sorted((n1,n2)))
                if key in edge_map:
                    old = edge_map[key]
                    if old[0] != n2 or old[1] != n1 or old[3] != 0:
                        raise ValueError("Inconsistent edge topology")
                    old[3] = cell(j,i)
                else:
                    edge_map[key] = [n1,n2,cell(j,i),0]
    groups = {k:[] for k in ["interior","axis","wafer","focus_ring","showerhead_inlet","blocked_showerhead","outlet"]}
    for edge in edge_map.values():
        n1,n2,c0,c1 = edge
        z = (coords[n1-1][0]+coords[n2-1][0])/2
        r = (coords[n1-1][1]+coords[n2-1][1])/2
        if c1: name = "interior"
        elif math.isclose(r,0,abs_tol=1e-12): name = "axis"
        elif math.isclose(z,0,abs_tol=1e-12): name = "wafer" if r < .150 else "focus_ring"
        elif math.isclose(r,rmax,abs_tol=1e-12): name = "outlet"
        else:
            opened = variant == "baseline" or (variant == "center_open" and r < .075) or (variant == "edge_open" and r > .075)
            name = "showerhead_inlet" if opened else "blocked_showerhead"
        groups[name].append(edge)
    ncells = nr*nz
    assert len(edge_map) == nr*(nz+1)+nz*(nr+1)
    assert groups['wafer'] and groups['showerhead_inlet'] and groups['outlet']
    # Geometric closure and positive area for every cell, before exporting.
    areas = [0.0]*ncells
    for n1,n2,c0,c1 in edge_map.values():
        x1,y1 = coords[n1-1]; x2,y2 = coords[n2-1]
        area = (x1*y2-x2*y1)/2
        areas[c0-1] += area
        if c1: areas[c1-1] -= area
    if min(areas) <= 0 or not math.isclose(sum(areas),height*rmax,rel_tol=1e-10):
        raise ValueError("Cell areas not positive or domain area not conserved")
    zone_types = {"interior":(2,"interior"),"axis":(37,"axis"),"wafer":(3,"wall"),"focus_ring":(3,"wall"),"showerhead_inlet":(20,"mass-flow-inlet"),"blocked_showerhead":(3,"wall"),"outlet":(5,"pressure-outlet")}
    lines = ['(0 "PECVD GAP CONNECTION TEST ONLY; dimensions in meters")','(2 2)',f'(10 (0 1 {len(coords):x} 0 2))',f'(10 (1 1 {len(coords):x} 1 2)(']
    lines.extend(f'{x:.12g} {y:.12g}' for x,y in coords)
    lines += ['))',f'(12 (0 1 {ncells:x} 0))',f'(12 (2 1 {ncells:x} 1 3))',f'(13 (0 1 {len(edge_map):x} 0))']
    first = 1
    zones = []
    for zid,(name,edges) in enumerate(groups.items(),start=3):
        if not edges: continue
        bc,zt = zone_types[name]
        lines.append(f'(13 ({zid:x} {first:x} {first+len(edges)-1:x} {bc:x} 2)(')
        lines.extend(' '.join(f'{v:x}' for v in edge) for edge in edges)
        lines.append('))')
        zones.append(f'(45 ({zid} {zt} {name})())')
        first += len(edges)
    lines += ['(45 (2 fluid neutral_gap)())',*zones]
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    return {"nodes":len(coords),"cells":ncells,"faces":len(edge_map),"boundary_face_counts":{k:len(v) for k,v in groups.items()},"minimum_cell_area_m2":min(areas),"native_Fluent_mesh_check":"not_yet_run","geometry":"gap_only_connection_test","dimensions_m":{"radial":rmax,"axial":height}}


def create_project(root: Path, project_id: str, variant: str, nr: int, nz: int) -> dict:
    path = project_path(root,project_id,False)
    if path.exists(): raise ValueError("Project already exists; use a new ID to preserve previous work")
    if variant not in VARIANTS: raise ValueError("Unknown showerhead variant")
    # Validate mesh before committing a project directory.
    path.mkdir(parents=True)
    try:
        mesh = generate_mesh(path/'gap.msh',variant,nr,nz)
        info = {"id":project_id,"variant":variant,"model_level":"nonreactive_connection_test_only","reported_baseline":baseline(),"conversions":conversions(),"mesh":mesh,"plasma_solution":"absent","deposition_solution":"absent","figure4_validation":"not_performed"}
        (path/'project.json').write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
        (path/'plasma_template.csv').write_text('r_m,z_m,ne_m3,Te_eV\n',encoding='ascii')
        (path/'wafer_flux_template.csv').write_text('r_m,net_film_mass_flux_kg_m2_s\n',encoding='ascii')
        (path/'research_gate.txt').write_text('This mesh tests the local Fluent connection. It omits the plenum, porous plates, plasma PDEs and reaction chemistry. It is not a reproduced PECVD reactor. No research deposition result may be inferred from this flow solve.\n',encoding='utf-8')
        return {"project_directory":str(path),**info}
    except Exception:
        for file in path.iterdir():
            if file.is_file(): file.unlink()
        path.rmdir()
        raise


def read_csv(path: Path, columns: tuple[str,...]) -> list[dict[str,float]]:
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(columns).issubset(reader.fieldnames):
            raise ValueError(f"Required CSV columns: {columns}")
        rows=[]
        for i,row in enumerate(reader,start=2):
            if i > 500002: raise ValueError("CSV too large")
            values = {key:float(row[key]) for key in columns}
            if not all(math.isfinite(x) for x in values.values()): raise ValueError(f"Non-finite number at line {i}")
            rows.append(values)
    if not rows: raise ValueError("CSV contains no data")
    return rows


def check_plasma_csv(path: Path, source_description: str) -> dict:
    if len(source_description.strip()) < 12: raise ValueError("Describe actual solver/measurement source and RF averaging")
    rows = read_csv(path,("r_m","z_m","ne_m3","Te_eV"))
    points = set()
    for row in rows:
        r,z = row['r_m'],row['z_m']
        if not (0<=r<=.16500001 and 0<=z<=.01500001): raise ValueError("Coordinates must be in SI meters within the gap")
        if row['ne_m3']<0 or row['Te_eV']<=0: raise ValueError("Require ne>=0 m^-3 and Te>0 eV")
        if (r,z) in points: raise ValueError("Duplicate (r,z) coordinate")
        points.add((r,z))
    summary={"rows":len(rows),"source_description":source_description,"validation":"format_and_range_only_not_physics","loaded_into_Fluent":False,"bounds":{k:[min(row[k] for row in rows),max(row[k] for row in rows)] for k in rows[0]}}
    (path.parent/'plasma_import_check.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def deposition_from_flux(path: Path, density: float, source_description: str) -> dict:
    density = positive(density,'Film density kg/m3')
    if len(source_description.strip())<12: raise ValueError("Describe actual flux source; net incorporated film mass flux is required")
    rows = read_csv(path,("r_m","net_film_mass_flux_kg_m2_s"))
    rows.sort(key=lambda row:row['r_m'])
    radii=[row['r_m'] for row in rows]
    if len(rows)<2 or len(set(radii))!=len(rows): raise ValueError("At least two unique radial locations required")
    if radii[0]<0 or radii[-1]>.15000001: raise ValueError("Wafer radius must lie within 0-0.150 m")
    if not math.isclose(radii[0],0,abs_tol=1e-9) or not math.isclose(radii[-1],.150,abs_tol=1e-9): raise ValueError("Full-wafer calculation requires data at r=0 and r=0.150 m")
    for row in rows:
        flux=positive(row['net_film_mass_flux_kg_m2_s'],'Net incorporated mass flux',True)
        row['DR_nm_min']=flux/density*6e10
        row['DR_A_min']=flux/density*6e11
    # Exact annular integral for linearly interpolated radial deposition rate.
    integral=0
    for a,b in zip(rows,rows[1:]):
        r1,r2=a['r_m'],b['r_m']; d1,d2=a['DR_nm_min'],b['DR_nm_min']
        slope=(d2-d1)/(r2-r1); intercept=d1-slope*r1
        integral += slope*(r2**3-r1**3)/3+intercept*(r2**2-r1**2)/2
    mean=2*integral/.150**2
    dmin=min(row['DR_nm_min'] for row in rows); dmax=max(row['DR_nm_min'] for row in rows)
    result={"source_description":source_description,"density_kg_m3":density,"conversion_only_not_a_deposition_solver":True,"annular_area_mean_nm_min":mean,"min_nm_min":dmin,"max_nm_min":dmax,"half_range_percent_of_area_mean":None if mean==0 else (dmax-dmin)/(2*mean)*100,"formula":"DR_nm/min = net incorporated film mass flux / density * 6e10; Angstrom/min uses 6e11"}
    with (path.parent/'wafer_deposition.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write_wafer_map(path.parent/'wafer_deposition.svg',rows,source_description)
    result['axisymmetric_map_file']='wafer_deposition.svg'
    (path.parent/'deposition_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def write_wafer_map(path: Path, rows: list[dict], source: str):
    """Render only the supplied radial flux result; no invented angular variations."""
    lo=min(row['DR_A_min'] for row in rows);hi=max(row['DR_A_min'] for row in rows)
    stops=[(68,1,84),(59,82,139),(33,145,140),(94,201,98),(253,231,37)]
    def color(value):
        u=0.5 if hi==lo else (value-lo)/(hi-lo)
        q=max(0,min(4,u*4));i=min(3,int(q));a=q-i
        return '#'+''.join(f'{round(stops[i][k]*(1-a)+stops[i+1][k]*a):02x}' for k in range(3))
    def interpolate(r):
        for a,b in zip(rows,rows[1:]):
            if a['r_m']<=r<=b['r_m']:
                w=(r-a['r_m'])/(b['r_m']-a['r_m'])
                return a['DR_A_min']*(1-w)+b['DR_A_min']*w
        return rows[-1]['DR_A_min']
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="640" viewBox="0 0 760 640">','<rect width="760" height="640" fill="white"/>','<g font-family="Arial,sans-serif" fill="#111">','<text x="30" y="30" font-size="19">Wafer deposition: supplied net film mass flux</text>','<text x="30" y="54" font-size="13">Axisymmetric radial reconstruction; 300 mm wafer; units: Angstrom/min</text>']
    # Outer-to-inner disks approximate the continuous radial interpolation.
    for i in range(200,0,-1):
        radius=i/200*.15
        parts.append(f'<circle cx="300" cy="320" r="{i*1.2:.2f}" fill="{color(interpolate(radius))}"/>')
    parts.extend(['<circle cx="300" cy="320" r="240" fill="none" stroke="#333"/>','<line x1="60" y1="570" x2="540" y2="570" stroke="#333"/>','<text x="55" y="590">-150 mm</text>','<text x="295" y="590">0</text>','<text x="495" y="590">150 mm</text>'])
    for i in range(100):
        value=hi-(hi-lo)*i/99
        parts.append(f'<rect x="590" y="{100+i*4}" width="25" height="4.1" fill="{color(value)}"/>')
    parts.extend([f'<text x="625" y="110">{hi:.6g}</text>',f'<text x="625" y="500">{lo:.6g}</text>',f'<text x="30" y="620" font-size="11">Source: {html.escape(source[:105])}</text>','</g></svg>'])
    path.write_text('\n'.join(parts),encoding='utf-8')
