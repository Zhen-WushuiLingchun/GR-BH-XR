# Reference Code Baseline

Date: 2026-06-28.

Purpose: record what GR-BH-XR should learn from established GRRT/ray-tracing
codes without vendoring or copying their source code.

## Review Boundary

- Repositories were shallow-cloned into a temporary directory only for
  inspection.
- No third-party source code was copied into this repository.
- License notes below are for planning hygiene, not legal advice.

## RAPTOR

- Repository: https://github.com/tbronzwaer/raptor
- Reviewed commit: `08cb9a2bba526dc7f0ee91e59ff7e178d0e709a1`
- Polarization branch checked: `b3e4c9ce8aa0527c4a337d60d6bf74002eff7910`
- License observed: GPL-3.0 in default branch.
- Language / dependencies: C, gcc, OpenMP, GSL, CBLAS, Python plotting.
- Relevant structure: `metric.c`, `integrator.c`, `radiative_transfer.c`,
  `j_nu.c`, `grmhd.c`, `raptor_harm_model.c`, `model.in`, `run.sh`.
- Input/output notes: default README describes HARM-oriented model input and
  generation of image-data plus spectrum-data files for plotting. The default
  public branch should be treated as the Phase 0 benchmark target.
- Polarization caveat: the polarization branch README states it is under
  construction and not yet publicly released under GPL, so do not copy or build
  against it. Use it only to understand later Stokes-transport direction.
- GR-BH-XR use: benchmark simplified GRRT behavior after the scalar transfer
  path exists; do not import code due GPL and branch caveats.

## AART

- Repository: https://github.com/iAART/aart
- Reviewed commit: `6e365357951381cb03d61982652ad533687d10b3`
- License observed: MIT.
- Language / dependencies: Python, NumPy/SciPy, matplotlib, h5py-related
  workflows, notebooks.
- Relevant structure: `aart_func/lb_f.py`, `aart_func/raytracing_f.py`,
  `aart_func/intensity_f.py`, `aart_func/visamp_f.py`,
  `aart_func/polarization_f.py`, `lensingbands.py`, `raytracing.py`.
- Key design lesson: separate lensing-band construction from ray tracing,
  image construction, visibility amplitudes, redshift, and polarization helper
  logic.
- Output notes: lensing-band and ray-tracing workflows write HDF5 datasets for
  Bardeen screen coordinates, hulls, grid points, source radius/angle/time, and
  radial momentum sign.
- GR-BH-XR use: adopt the design principle that the critical-curve/photon-ring
  neighborhood needs nonuniform/adaptive treatment. Do not reduce Phase 1 to a
  uniform RGB shader.

## Odyssey

- Repository: https://github.com/hungyipu/Odyssey
- Reviewed commit: `7527549a4215b5382bceec9d0c1d9280bd33be2e`
- License observed: GPL through `COPYING`.
- Language / dependencies: CUDA C/C++.
- Relevant structure: `src/main.cpp`, `src/task1.cpp`, `src/task2.cpp`,
  `src/Odyssey.cu`, `src/Odyssey_def.h`, `src/Odyssey_def_fun.h`.
- Kernel/task pattern: `main.cpp` sets black-hole/render parameters, each task
  owns setup/compute/after stages, and CUDA kernels perform ray updates and
  task-specific work.
- Design lesson: keep task-specific physics work separate from GPU launch,
  device memory, and output plumbing. This maps well to future GR-BH-XR debug
  buffers such as capture mask, redshift map, and time-delay map.
- Numerical lesson: the README highlights adaptive-step Runge-Kutta ray updates
  inside the GPU task loop.
- GR-BH-XR use: architecture reference for a later GPU port after the CPU
  reference solver is validated. Do not import code due GPL.

## ipole

- Repository: https://github.com/AFD-Illinois/ipole
- Reviewed commit: `7f7a482cf91125aeeeb9c431485bba680e8941d7`
- License observed: BSD-3-Clause.
- Language / dependencies: C, HDF5, GSL, OpenMP-related build concerns.
- Relevant structure: `src/geodesics.c`, `src/geometry.c`,
  `src/model_geodesics.c`, `src/model_radiation.c`, `src/tetrads.c`,
  `src/hdf5_utils.c`, `model/`, `tests/`.
- Output notes: README describes image and trace outputs, including per-pixel
  trace diagnostics and Stokes-capable image products.
- Design lesson: trace output for selected pixels is valuable for debugging
  transfer maps and should inspire GR-BH-XR's Phase 1 ray diagnostics.
- Scope lesson: ipole itself warns it is not a general-purpose imaging code and
  should be validated in the target regime. Treat it as a later polarized-GRRT
  benchmark, not as a first implementation dependency.

## grtrans

- Repository: https://github.com/jadexter/grtrans
- Reviewed commit: `c76cb11fa1396516f38ba6f972c68fbb5b5ae984`
- License observed: MIT.
- Language / dependencies: Fortran 90/77 with Python wrappers; cfitsio.
- Relevant structure: `geodesics.f90`, `kerr.f90`, `camera.f90`,
  `radtrans_integrate.f90`, `fluid_model_thindisk.f90`,
  `fluid_model_harm.f90`, `grtrans_batch.py`, `run_grtrans_test_problems_public.py`.
- Output notes: README describes camera coordinates `(alpha, beta)`, spectra,
  observed intensities, Stokes parameter count, geodesic debug output, and many
  fluid/emission model choices.
- Design lesson: keep geodesic parameters, camera grid, fluid model, emission
  model, and debug-output controls explicit and scriptable.
- GR-BH-XR use: later benchmark for polarized and model-rich GRRT; too broad
  for Phase 1 implementation.

## Phase 1 Design Implications

- Start CPU Kerr work with an explicit camera/screen map and traceable
  diagnostics before any GPU or XR path.
- Preserve per-ray diagnostics: Hamiltonian residual, event class, conserved
  quantities, crossing order, and selected-pixel trace output.
- Keep benchmark adapters separate from solver code so GPL references can be
  compared without contaminating implementation.
- HDF5 is a good candidate for lens maps and transfer caches, but Phase 1 may
  start with a simpler documented format if HDF5 setup blocks progress.
