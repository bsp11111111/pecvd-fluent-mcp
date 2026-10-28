import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from pecvd_mcp.bridge import FluentBridge
from pecvd_mcp.model import conversions, create_project, deposition_from_flux, check_plasma_csv, local_file, project_path


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def write_csv(self,name,rows):
        path=self.root/name
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return path

    def test_sccm_mass_molar_conversion(self):
        c=conversions()
        self.assertAlmostEqual(c['pressure_Pa'],266.6447368421,places=7)
        self.assertAlmostEqual(c['SiH4_mole_fraction'],280/2620)
        # Independent pure-gas standard density mixture computation.
        expected=(280*.03211726+2340*.01703052)/.02241396954*1e-6/60
        self.assertAlmostEqual(c['total_mass_flow_kg_s'],expected,delta=expected*2e-6)
        self.assertGreater(c['SiH4_mass_fraction'],c['SiH4_mole_fraction'])

    def test_three_meshes_and_conserved_total_inlet_flow(self):
        counts=[]
        for variant in ['baseline','center_open','edge_open']:
            p=create_project(self.root,variant,variant,22,4)
            self.assertEqual(p['mesh']['cells'],88)
            self.assertEqual(p['mesh']['nodes'],115)
            self.assertEqual(p['mesh']['faces'],202)
            counts.append(p['mesh']['boundary_face_counts']['showerhead_inlet'])
            self.assertEqual(p['plasma_solution'],'absent')
            self.assertEqual(p['deposition_solution'],'absent')
            self.assertEqual(p['conversions']['total_mass_flow_kg_s'],conversions()['total_mass_flow_kg_s'])
            self.assertIn('(2 2)',(self.root/variant/'gap.msh').read_text())
        self.assertEqual(counts,[22,10,12])

    def test_refuse_overwrite_and_bad_grid(self):
        create_project(self.root,'same','baseline',22,4)
        before=(self.root/'same/gap.msh').read_bytes()
        with self.assertRaises(ValueError):create_project(self.root,'same','baseline',44,4)
        self.assertEqual(before,(self.root/'same/gap.msh').read_bytes())
        for nr,nz in [(23,4),(22,0),(True,10),(528,192)]:
            with self.assertRaises(ValueError):create_project(self.root,'bad','baseline',nr,nz)
            self.assertFalse((self.root/'bad').exists())

    def test_sandbox_paths(self):
        for name in ['../escape','x/y','C:\\Windows','', 'a'*65]:
            with self.assertRaises(ValueError):project_path(self.root,name,False)
        outside=self.root/'secret.txt';outside.write_text('not accessible')
        project=self.root/'inside';project.mkdir()
        with self.assertRaises(ValueError):local_file(project,'../secret.txt',('.txt',))
        try:(project/'link.txt').symlink_to(outside)
        except OSError:return
        with self.assertRaises(ValueError):local_file(project,'link.txt',('.txt',))

    def test_flux_conversion_and_annular_mean(self):
        # Linear profile: center 30 nm/min, edge 60 nm/min; exact area mean 50.
        path=self.write_csv('flux.csv',[{'r_m':0,'net_film_mass_flux_kg_m2_s':1e-6},{'r_m':.15,'net_film_mass_flux_kg_m2_s':2e-6}])
        result=deposition_from_flux(path,2000,'unit-test manufactured flux, not a solver result')
        self.assertAlmostEqual(result['annular_area_mean_nm_min'],50)
        self.assertAlmostEqual(result['half_range_percent_of_area_mean'],30)
        with (self.root/'wafer_deposition.csv').open() as stream:
            output=list(csv.DictReader(stream))
        self.assertAlmostEqual(float(output[0]['DR_A_min']),300)
        self.assertTrue(result['conversion_only_not_a_deposition_solver'])
        self.assertIn('Axisymmetric radial reconstruction',(self.root/'wafer_deposition.svg').read_text())

    def test_reject_bad_flux_or_density(self):
        path=self.write_csv('flux.csv',[{'r_m':0,'net_film_mass_flux_kg_m2_s':1e-6},{'r_m':.15,'net_film_mass_flux_kg_m2_s':-2e-6}])
        with self.assertRaises(ValueError):deposition_from_flux(path,2000,'negative test input only')
        for density in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):deposition_from_flux(path,density,'invalid density test input')
        path=self.write_csv('partial.csv',[{'r_m':0,'net_film_mass_flux_kg_m2_s':1e-6},{'r_m':.1,'net_film_mass_flux_kg_m2_s':1e-6}])
        with self.assertRaises(ValueError):deposition_from_flux(path,2000,'incomplete wafer test input')

    def test_plasma_table_is_only_schema_validation(self):
        path=self.write_csv('plasma.csv',[{'r_m':0,'z_m':0,'ne_m3':1e15,'Te_eV':2},{'r_m':.15,'z_m':.015,'ne_m3':2e15,'Te_eV':3}])
        result=check_plasma_csv(path,'unit-test manufactured values, not plasma computation')
        self.assertFalse(result['loaded_into_Fluent'])
        self.assertEqual(result['validation'],'format_and_range_only_not_physics')
        path=self.write_csv('invalid.csv',[{'r_m':0,'z_m':.02,'ne_m3':1e15,'Te_eV':2}])
        with self.assertRaises(ValueError):check_plasma_csv(path,'out of domain test input')

    def test_bridge_lifecycle_limits_and_license_failure(self):
        bridge=FluentBridge(self.root)
        with self.assertRaises(ValueError):bridge.iterate('not_launched')
        bridge.new_project('x',nr=22,nz=4)
        with self.assertRaises(ValueError):bridge.launch('x',processors=0)
        calls=[]
        def no_license(**kwargs):
            calls.append(kwargs);raise RuntimeError('test-only license rejection')
        bridge.session_factory=no_license
        with self.assertRaises(RuntimeError):bridge.launch('x')
        self.assertEqual(calls[0]['product_version'],'24.1')
        self.assertEqual(calls[0]['dimension'],2)
        self.assertIsNone(bridge.session)
        self.assertEqual(bridge.phase,'disconnected')
        self.assertFalse(list((self.root/'x').glob('*.cas.h5')))

    def test_wrong_solver_version_is_closed(self):
        class WrongVersion:
            closed=False
            def get_fluent_version(self):return '25.1.0'
            def exit(self):self.closed=True
        fake=WrongVersion()
        bridge=FluentBridge(self.root,session_factory=lambda **kwargs:fake)
        bridge.new_project('x',nr=22,nz=4)
        with self.assertRaises(ValueError):bridge.launch('x')
        self.assertTrue(fake.closed)
        self.assertIsNone(bridge.session)

    def test_accept_official_version_enum(self):
        from ansys.fluent.core.utils.fluent_version import FluentVersion
        class ExpectedVersion:
            def get_fluent_version(self):return FluentVersion.v241
            def exit(self):pass
        bridge=FluentBridge(self.root,session_factory=lambda **kwargs:ExpectedVersion())
        bridge.new_project('x',nr=22,nz=4)
        result=bridge.launch('x')
        self.assertEqual(result['phase'],'launched')
        bridge.close()


if __name__=='__main__':unittest.main()
