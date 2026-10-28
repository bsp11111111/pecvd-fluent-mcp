"""Check referenced API paths against official generated 24.1 classes, not a solver run."""
import unittest


class SDKContractTests(unittest.TestCase):
    def test_241_is_supported_and_setting_paths_exist(self):
        from ansys.fluent.core.utils.fluent_version import FluentVersion
        from ansys.fluent.core.generated.solver import settings_241
        self.assertIn('24.1.0',[v.value for v in FluentVersion])
        paths=[
            'setup.general.solver.two_dim_space','setup.general.solver.type','setup.general.solver.time',
            'setup.general.operating_conditions.operating_pressure','setup.models.energy.enabled','setup.models.viscous.model',
            'setup.materials.fluid.*.density.option','setup.materials.fluid.*.molecular_weight.value',
            'setup.materials.fluid.*.viscosity.option','setup.materials.fluid.*.viscosity.value',
            'setup.materials.fluid.*.specific_heat.option','setup.materials.fluid.*.specific_heat.value',
            'setup.materials.fluid.*.thermal_conductivity.option','setup.materials.fluid.*.thermal_conductivity.value',
            'setup.boundary_conditions.mass_flow_inlet.*.momentum.mass_flow_rate.value',
            'setup.boundary_conditions.mass_flow_inlet.*.momentum.supersonic_gauge_pressure.value',
            'setup.boundary_conditions.mass_flow_inlet.*.thermal.total_temperature.value',
            'setup.boundary_conditions.pressure_outlet.*.momentum.gauge_pressure.value',
            'setup.boundary_conditions.pressure_outlet.*.thermal.t0.value',
            'setup.boundary_conditions.wall.*.thermal.thermal_bc','setup.boundary_conditions.wall.*.thermal.t.value',
            'solution.initialization.hybrid_initialize','solution.run_calculation.iterate','file.read_mesh',
            'file.start_transcript','file.stop_transcript','file.write_case_data',
        ]
        for path in paths:
            with self.subTest(path=path):
                cls=settings_241.root
                for part in path.split('.'):
                    cls=cls.child_object_type if part=='*' else cls._child_classes[part]


if __name__=='__main__':unittest.main()
