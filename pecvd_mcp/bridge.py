from __future__ import annotations

import atexit
import contextlib
import importlib.metadata
import json
import os
import platform
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from .model import baseline, check_plasma_csv, conversions, create_project, deposition_from_flux, local_file, project_path

PACKAGE_ROOT = Path(os.environ.get('PECVD_PACKAGE_ROOT', Path(__file__).resolve().parent.parent)).resolve()


class FluentBridge:
    """Owns one separately launched Fluent instance; never attaches to other jobs."""

    def __init__(self, workspace: Path | None = None, session_factory=None):
        self.workspace = (workspace or Path(os.environ.get('PECVD_WORKSPACE', PACKAGE_ROOT/'runs'))).resolve()
        self.session = None
        self.project_id = None
        self.phase = 'disconnected'
        self.lock = threading.RLock()
        self.session_factory = session_factory

    def config(self):
        path = PACKAGE_ROOT/'local-config.json'
        return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}

    def executable(self):
        custom = self.config().get('fluent_executable')
        candidates = [Path(custom)] if custom else []
        root = os.environ.get('AWP_ROOT241')
        if root: candidates.append(Path(root)/'fluent/ntbin/win64/fluent.exe')
        candidates.append(Path(r'C:\Program Files\ANSYS Inc\v241\fluent\ntbin\win64\fluent.exe'))
        for path in candidates:
            if path.is_file() and path.name.lower() == 'fluent.exe': return path.resolve()
        return None

    def doctor(self):
        versions = {}
        for dependency in ['mcp','ansys-fluent-core']:
            try: versions[dependency] = importlib.metadata.version(dependency)
            except importlib.metadata.PackageNotFoundError: versions[dependency] = None
        exe = self.executable()
        return {
            'python':platform.python_version(),'system':platform.system(),'dependencies':versions,
            'target_version':'ANSYS Fluent 2024 R1 / 24.1','fluent_executable':str(exe) if exe else None,
            'workspace':str(self.workspace),'phase':self.phase,'active_project':self.project_id,
            'license_verified':self.session is not None,
            'research_status':'No plasma equations, neutral reaction mechanism or surface reaction model installed by this bridge.',
        }

    def audit(self, action: str, details: dict):
        if self.project_id:
            path=project_path(self.workspace,self.project_id)
            with (path/'operations.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'action':action,'phase':self.phase,**details},ensure_ascii=False,default=str)+'\n')

    def new_project(self, project_id: str, variant='baseline', nr=132, nz=24):
        with self.lock:
            return create_project(self.workspace,project_id,variant,nr,nz)

    def launch(self, project_id: str, show_gui=True, processors=2):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            if self.session is not None: raise ValueError('A managed Fluent session is already running; save and close it first')
            path=project_path(self.workspace,project_id)
            if isinstance(processors,bool) or not isinstance(processors,int) or not 1<=processors<=8: raise ValueError('Use 1-8 processors')
            if self.session_factory is None:
                exe=self.executable()
                if not exe: raise ValueError('Fluent 2024 R1 executable not found; edit local-config.json using the example')
                import ansys.fluent.core as pyfluent
                factory=pyfluent.launch_fluent
            else:
                exe=None; factory=self.session_factory
            self.session=factory(product_version='24.1',dimension=2,precision='double',processor_count=processors,mode='solver',ui_mode='gui' if show_gui else 'no_gui',cwd=str(path),fluent_path=str(exe) if exe else None,start_timeout=180,start_transcript=False,cleanup_on_exit=True)
            try:
                version=self.session.get_fluent_version()
                actual=str(getattr(version,'value',version))
                if not actual.startswith('24.1'): raise ValueError(f'Expected 24.1, got {actual}')
            except Exception:
                self.session.exit();self.session=None;raise
            self.project_id=project_id;self.phase='launched'
            self.audit('launch',{'fluent_version':actual})
            return self.doctor()

    def active(self, project_id: str):
        if self.session is None or project_id != self.project_id: raise ValueError('Launch this project in the managed session first')
        return project_path(self.workspace,project_id),self.session.settings

    def load_gap_mesh(self, project_id: str):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            path,settings=self.active(project_id)
            settings.file.read_mesh(file_name=str(path/'gap.msh'))
            settings.setup.general.solver.two_dim_space='axisymmetric'
            settings.file.start_transcript(file_name=str(path/'mesh-check.trn'))
            try: self.session.tui.mesh.check()
            finally: settings.file.stop_transcript()
            self.phase='mesh_loaded_check_requires_review'
            self.audit('load_gap_mesh',{'check_log':'mesh-check.trn'})
            return {'phase':self.phase,'check_log':str(path/'mesh-check.trn'),'next':'Read native Fluent mesh-check output: positive volumes, no topology errors; acknowledge before configuring.'}

    def configure_connection_test(self, project_id: str, acknowledge_mesh_check: bool = False):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            path,s=self.active(project_id)
            if self.phase!='mesh_loaded_check_requires_review' or not acknowledge_mesh_check:
                raise ValueError('Load gap mesh, review native mesh-check transcript and acknowledge first')
            p=baseline()['reported'];c=conversions()
            # Explicit numerical test constants, not claimed SiH4/NH3 transport data.
            props={'viscosity_Pa_s':1.2e-5,'cp_J_kg_K':2000.0,'thermal_conductivity_W_m_K':0.04}
            try:
                s.setup.general.solver.type='pressure-based'
                s.setup.general.solver.time='steady'
                s.setup.general.solver.two_dim_space='axisymmetric'
                s.setup.general.operating_conditions.operating_pressure=0
                s.setup.models.energy.enabled=True
                s.setup.models.viscous.model='laminar'
                # Fresh Fluent meshes use the default air material. Replace its properties
                # with a single ideal-gas surrogate; species and reactions remain OFF.
                air=s.setup.materials.fluid['air']
                air.density.option='ideal-gas'
                air.molecular_weight.value=c['mixture_molecular_weight_kg_per_kmol']
                for key,value in [('viscosity',props['viscosity_Pa_s']),('specific_heat',props['cp_J_kg_K']),('thermal_conductivity',props['thermal_conductivity_W_m_K'])]:
                    getattr(air,key).option='constant';getattr(air,key).value=value
                inlet=s.setup.boundary_conditions.mass_flow_inlet['showerhead_inlet']
                inlet.momentum.mass_flow_rate.value=c['total_mass_flow_kg_s']
                inlet.momentum.supersonic_gauge_pressure.value=c['pressure_Pa']
                inlet.thermal.total_temperature.value=p['inlet_temperature_K']
                outlet=s.setup.boundary_conditions.pressure_outlet['outlet']
                outlet.momentum.gauge_pressure.value=c['pressure_Pa']
                outlet.thermal.t0.value=p['reaction_wall_temperature_K']
                for name in ['wafer','focus_ring']:
                    wall=s.setup.boundary_conditions.wall[name]
                    wall.thermal.thermal_bc='Temperature';wall.thermal.t.value=p['substrate_temperature_K']
                if 'blocked_showerhead' in s.setup.boundary_conditions.wall.get_object_names():
                    wall=s.setup.boundary_conditions.wall['blocked_showerhead']
                    wall.thermal.thermal_bc='Temperature';wall.thermal.t.value=p['showerhead_wall_temperature_K']
                self.phase='connection_test_configured'
            except Exception:
                self.phase='configuration_failed';self.audit('configuration_failed',{});raise
            details={'assumed_test_properties':props,'boundary_conversions':c,'physics':'single neutral surrogate, laminar, ideal gas, energy; NO plasma, species chemistry or deposition'}
            (path/'connection-test-settings.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
            self.audit('configure_connection_test',details)
            return {'phase':self.phase,**details}

    def initialize(self, project_id: str):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            _,s=self.active(project_id)
            if self.phase!='connection_test_configured': raise ValueError('Configure the connection test first')
            s.solution.initialization.hybrid_initialize()
            self.phase='initialized';self.audit('initialize',{})
            return {'phase':self.phase}

    def iterate(self, project_id: str, iterations: int = 25):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            path,s=self.active(project_id)
            if isinstance(iterations,bool) or not isinstance(iterations,int) or not 1<=iterations<=500: raise ValueError('Use 1-500 iterations per call')
            if self.phase not in ['initialized','iterated']: raise ValueError('Initialize the configured connection test first')
            log=f'iterations-{datetime.now().strftime("%Y%m%d-%H%M%S-%f")}.trn'
            s.file.start_transcript(file_name=str(path/log))
            try:s.solution.run_calculation.iterate(iter_count=iterations)
            finally:s.file.stop_transcript()
            self.phase='iterated';self.audit('iterate',{'iterations':iterations,'transcript':log})
            return {'phase':self.phase,'transcript':str(path/log),'converged':'not_assessed','research_validation':'not_performed'}

    def save(self, project_id: str):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            path,s=self.active(project_id)
            # Always use a new name; do not overwrite previous work.
            name='connection-test-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.cas.h5'
            s.file.write_case_data(file_name=str(path/name))
            self.audit('save_case_data',{'case':name})
            return {'case':str(path/name),'phase':self.phase,'notice':'Case/data are connection-test artifacts, not validated PECVD results'}

    def read_artifact(self, project_id: str, relative_path: str):
        with self.lock:
            path=local_file(project_path(self.workspace,project_id),relative_path,('.json','.jsonl','.trn','.csv','.txt'))
            with path.open(encoding='utf-8',errors='replace') as stream: text=stream.read(16001)
            return {'file':str(path),'text':text[:16000],'truncated':len(text)>16000}

    def plasma_check(self, project_id: str, csv_name: str, source_description: str):
        with self.lock:
            path=local_file(project_path(self.workspace,project_id),csv_name,('.csv',))
            return check_plasma_csv(path,source_description)

    def flux_to_rate(self, project_id: str, csv_name: str, density_kg_m3: float, source_description: str):
        with self.lock:
            path=local_file(project_path(self.workspace,project_id),csv_name,('.csv',))
            return deposition_from_flux(path,density_kg_m3,source_description)

    def close(self):
        with self.lock, contextlib.redirect_stdout(sys.stderr):
            if self.session is not None:
                self.session.exit();self.session=None
            self.phase='disconnected';self.project_id=None
            return {'phase':self.phase}


bridge=FluentBridge()
atexit.register(bridge.close)
