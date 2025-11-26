"""Work chain to calculate the energy levels of a defect structure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiida import engine, orm
from aiida_quantumespresso.workflows.protocols.utils import ProtocolMixin
from aiida_shell import ShellJob
from aiida_vasp.workchains.v2.vasp import VaspWorkChain, potential_family_validator

if TYPE_CHECKING:
    from plumpy import WorkChainSpec


class EnergyLevelsWorkChain(engine.WorkChain, ProtocolMixin):
    """Work chain to calculate the energy levels of a defect structure."""

    @classmethod
    def define(cls, spec: WorkChainSpec) -> None:
        super().define(spec)

        spec.expose_inputs(
            process_class=VaspWorkChain,
            exclude=("structure", "potential_family", "potential_mapping"),
            namespace="relax",
        )
        spec.expose_inputs(
            process_class=VaspWorkChain, exclude=("structure", "potential_family", "potential_mapping"), namespace="scf"
        )
        spec.input(
            "structure",
            valid_type=(orm.StructureData, orm.CifData),
            required=True,
        )
        spec.input(
            "potential_family",
            valid_type=orm.Str,
            required=True,
            validator=potential_family_validator,
        )
        spec.input(
            "potential_mapping",
            valid_type=orm.Dict,
            required=True,
        )
        spec.output("relaxed_structure", valid_type=orm.StructureData)
        spec.output("energy_levels", valid_type=orm.ArrayData)

        spec.outline(cls.relax, cls.scf, cls.assign_outputs)

    @classmethod
    def get_protocol_filepath(cls):
        """Return ``pathlib.Path`` to the ``.yaml`` file that defines the protocols."""
        from importlib_resources import files

        from aiida_pl.workchains import protocols

        return files(protocols) / "levels.yaml"

    @classmethod
    def get_builder_from_protocol(
        cls,
        structure: orm.StructureData,
        vasp_gam_code: orm.Code,
        vasp_std_code: orm.Code,
        options: dict | orm.Dict,
        overrides=None,
    ):
        """Get a fully populated builder based on the protocol."""
        inputs = cls.get_protocol_inputs(protocol="default", overrides=overrides)

        builder = cls.get_builder()

        builder.potential_family = inputs["potential_family"]

        if "potential_mapping" in inputs:
            builder.potential_mapping = inputs["potential_mapping"]
        else:
            builder.potential_mapping = {element: element for element in structure.get_symbols_set()}

        kpoints = orm.KpointsData()
        kpoints.set_kpoints_mesh([1, 1, 1])

        relax_inputs = {"code": vasp_gam_code, "kpoints": kpoints, "options": options}
        relax_inputs.update(inputs["relax"])

        scf_inputs = {"code": vasp_std_code, "kpoints": kpoints, "options": options}
        scf_inputs.update(inputs["scf"])

        builder.structure = structure
        builder.relax = relax_inputs
        builder.scf = scf_inputs

        return builder

    def relax(self) -> engine.ExitCode | None:
        """Relax the geometry of the inputs structure."""
        inputs = self.exposed_inputs(VaspWorkChain, "relax")
        inputs["structure"] = self.inputs.structure
        inputs["potential_family"] = self.inputs.potential_family
        inputs["potential_mapping"] = self.inputs.potential_mapping

        return {"relax": self.submit(VaspWorkChain, inputs)}

    def scf(self) -> engine.ExitCode | None:
        """Run the SCF."""
        self.out("relaxed_structure", self.ctx["relax"].outputs.structure)

        inputs = self.exposed_inputs(VaspWorkChain, "scf")
        inputs["structure"] = self.ctx["relax"].outputs.structure
        inputs["potential_family"] = self.inputs.potential_family
        inputs["potential_mapping"] = self.inputs.potential_mapping

        additional_retrieve_list = inputs["options"].get("additional_retrieve_list") or []

        if "EIGENVAL" not in additional_retrieve_list:
            options = inputs["options"].get_dict()
            options["additional_retrieve_list"] = (*additional_retrieve_list, "EIGENVAL")
            inputs["options"] = options

        return {"scf": self.submit(VaspWorkChain, inputs)}

    def assign_outputs(self) -> engine.ExitCode | None:
        """Assign the outputs."""
        self.out("energy_levels", parse_eigenval(self.ctx["scf"].outputs.retrieved)['energy_levels'])


@engine.calcfunction
def parse_eigenval(retrieved_data: orm.FolderData):
    """Parse the Gamma-point energy-levels"""
    from parsevasp.eigenval import Eigenval

    with retrieved_data.open("EIGENVAL") as handle:
        eigenval = Eigenval(file_handler=handle)

    energy_levels = orm.ArrayData()
    energy_levels.set_array("up_levels", eigenval.get_eigenvalues()[0, 0, :])
    energy_levels.set_array("down_levels", eigenval.get_eigenvalues()[1, 0, :])

    return {"energy_levels": energy_levels, "number_of_electrons": orm.Int(eigenval.get_metadata()["some_num"])}


@engine.calcfunction
def get_remote_path(remote_data):
    return orm.Str(remote_data.get_remote_path())
