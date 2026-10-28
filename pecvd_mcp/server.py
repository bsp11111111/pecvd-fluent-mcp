"""STDIO MCP only. Never opens an HTTP port or exposes arbitrary shell/UDF code."""
from mcp.server.fastmcp import FastMCP
from .bridge import bridge
from .model import baseline, conversions

mcp=FastMCP('PECVD Fluent 2024 R1')


@mcp.tool()
def check_environment() -> dict:
    """Detect local Fluent path, Python/dependencies and managed-session state; no solver launched."""
    return bridge.doctor()


@mcp.tool()
def read_paper_baseline() -> dict:
    """Reported paper parameters, source pages, assumptions and missing reproduction inputs."""
    return {'reference':baseline(),'converted_units':conversions()}


@mcp.tool()
def create_connection_project(project_id: str, variant: str='baseline', nr: int=132, nz: int=24) -> dict:
    """Generate new gap-only connection-test mesh in meters. NOT a full PECVD reactor. Variants: baseline/center_open/edge_open. Never overwrites a project."""
    return bridge.new_project(project_id,variant,nr,nz)


@mcp.tool()
def launch_fluent(project_id: str, show_gui: bool=True, processors: int=2) -> dict:
    """Launch a separate local Fluent 24.1 session, consuming a local license. Does not attach to an existing GUI job."""
    return bridge.launch(project_id,show_gui,processors)


@mcp.tool()
def load_and_check_gap_mesh(project_id: str) -> dict:
    """Read generated mesh and run native Fluent mesh check; review mesh-check.trn before proceeding."""
    return bridge.load_gap_mesh(project_id)


@mcp.tool()
def configure_nonreactive_connection_test(project_id: str, acknowledge_mesh_check: bool=False) -> dict:
    """Configure neutral ideal-gas surrogate/laminar flow/energy with explicitly assumed properties. No plasma, species chemistry or deposition. Requires reviewed native mesh check."""
    return bridge.configure_connection_test(project_id,acknowledge_mesh_check)


@mcp.tool()
def initialize_connection_test(project_id: str) -> dict:
    """Hybrid-initialize the configured connection test; no research result implied."""
    return bridge.initialize(project_id)


@mcp.tool()
def iterate_connection_test(project_id: str, iterations: int=25) -> dict:
    """Run 1-500 iterations, save transcript; completion does not assert convergence or validation."""
    return bridge.iterate(project_id,iterations)


@mcp.tool()
def save_case_and_data(project_id: str) -> dict:
    """Save real managed Fluent case/data with a fresh timestamp; never fabricates a case file."""
    return bridge.save(project_id)


@mcp.tool()
def read_project_text(project_id: str, relative_path: str) -> dict:
    """Read up to 16000 characters of a project log/CSV/JSON; cannot access files outside workspace project."""
    return bridge.read_artifact(project_id,relative_path)


@mcp.tool()
def check_external_plasma_table(project_id: str, csv_name: str, source_description: str) -> dict:
    """Validate actual external r_m,z_m,ne_m3,Te_eV table. Format/range only; does not solve plasma or install fields in Fluent."""
    return bridge.plasma_check(project_id,csv_name,source_description)


@mcp.tool()
def convert_actual_wafer_flux_to_deposition(project_id: str, csv_name: str, density_kg_m3: float, source_description: str) -> dict:
    """Convert actual NET incorporated film mass flux to nm/min and Angstrom/min, with radial area mean. Requires supplied film density and flux source; not a kinetics solver."""
    return bridge.flux_to_rate(project_id,csv_name,density_kg_m3,source_description)


@mcp.tool()
def close_managed_fluent() -> dict:
    """Close only this bridge's Fluent instance; save first if you need the current solution."""
    return bridge.close()


def main():
    mcp.run(transport='stdio')


if __name__=='__main__':main()
