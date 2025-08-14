---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.17.2
  kernelspec:
    display_name: DEFECT
    language: python
    name: python3
---

# Energy levels workflow

In this notebook, we show how to run the `EnergyLevelsWorkChain`, which can be used to calculate the energy levels of the ground state structure, as well as the transition dipole moments for the defect levels.

First we'll import some basic AiiDA modules and load the profile:

```python
from aiida import orm, engine, load_profile

load_profile()
```

Next, let's create a structure for testing the workflow.
Bulk silicon doesn't make too much sense for the defect energy levels, but it'll do for testing:

```python
from ase.build import bulk

structure = orm.StructureData(ase=bulk('Si', 'diamond', 5.4))
```

Now we're ready to set up the workflow inputs!
The cell below:

1. Defines the `options` we'll set for each VASP calculation in the workflow.
   These mainly determine the resources we are using.
2. Uses the `get_builder_from_protocol()` method to obtain an AiiDA "process builder", fully populated with inputs based on the default protocol.
3. Returns the `builder` variable, so you can see the full inputs of the workflow.

```python
from aiida_pl.workchains import EnergyLevelsWorkChain

options = {
    'resources': {
        'num_machines': 1,
        'tot_num_mpiprocs': 64,
        'num_cores_per_mpiproc': 1
    },
    'account': 'pawsey1141',
    'queue_name': 'debug',
    'max_memory_kb': int(115 * 1024 * 1023),
}

builder = EnergyLevelsWorkChain.get_builder_from_protocol(
    structure=structure,
    vasp_gam_code=orm.load_code('vasp-6.5.1_gam@pawsey'),
    vasp_std_code=orm.load_code('vasp-6.5.1_std@pawsey'),
    tdm_script=orm.load_code('get_tdm@pawsey-direct'),
    options=options
)
builder
```

Now it's time to run the workflow! 🚀
We'll use the `run()` function of the `engine` module to do so.

```{important}
The `run()` function will run the workflow in the current Python instance.
Since we'll actually run VASP on the remote machine, **the workflow can take a while to complete.**
If you interrupt the process at any stage, you will kill the workflow and its subprocesses.
```

```python
results = engine.run(builder)
```

```{attention}
This is the end of the tutorial material, so far.
More to come soon! 👋
```
