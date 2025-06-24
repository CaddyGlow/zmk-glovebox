Glovebox Documentation
======================

**Glovebox** is a comprehensive tool for ZMK keyboard firmware management that transforms keyboard layouts through a multi-stage pipeline.

.. code-block:: text

   Layout Editor → JSON File → ZMK Files → Firmware → Flash
     (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)

Quick Start
-----------

Get started with Glovebox quickly:

.. toctree::
   :maxdepth: 2

   user/getting-started
   user/keymap-version-management

User Guide
----------

Complete user documentation:

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   user/README

Developer Guide
---------------

Documentation for developers working on Glovebox:

.. toctree::
   :maxdepth: 2
   :caption: Developer Documentation

   dev/README
   dev/architecture/overview
   dev/testing
   dev/conventions/code-style
   dev/shared-cache-coordination

Technical Reference
-------------------

Technical specifications and references:

.. toctree::
   :maxdepth: 2
   :caption: Technical Documentation

   technical/README
   technical/keymap_file_format
   technical/caching-system

API Reference
-------------

Auto-generated API documentation:

.. toctree::
   :maxdepth: 1
   :caption: API Documentation

   api/index

Domain Architecture
-------------------

Core domains and their documentation:

.. toctree::
   :maxdepth: 2
   :caption: Domain Documentation

   dev/domains/layout-domain
   dev/domains/firmware-domain
   dev/domains/config-domain

Implementation Plans
--------------------

Current and completed implementation plans:

.. toctree::
   :maxdepth: 2
   :caption: Implementation Documentation

   implementation/completed/keymap_version_management
   implementation/completed/firmware-command-refactoring
   implementation/completed/shared-cache-coordination-system

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`