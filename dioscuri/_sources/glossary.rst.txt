.. _gemini-glossary:

Glossary
===========================

This page provides an overview of the definitions of various terms used in this manual and the GEMINI platform itself.


Application
    An interactive tool within the platform that can be used to execute on-demand calculations and/or visualizations for detailed analyses of various assets or processes of the physical system. 


Asset
    A part of the physical system, often corresponding to a unit operation, that
    can be treated independently or as part of a larger system. The digital
    counterpart of an asset in Diagram Builder is called a "unit".


Calculated Data
    The output tags computed by the modules. Stored separately from the plant data to prevent conflicts or accidental overwriting of data.


Database
    An external storage for tag values.


Diagram
    The digital representation of a physical plant resembling a process flow diagram. Consists of a collection of units connected to each other.


Diagram builder
    The application used to create the diagram of the physical plant. 


GUI
    Acronym for Graphical User Interface, the visual interface through which a user can interact with the GEMINI framework, modules, and applications.


Model
    A script that takes inputs, performs calculations, and returns outputs.
    Static models are pure input-output; dynamic models maintain internal state
    across executions.


Module
    A periodically executed script designed to automatically call a (collection of) model(s) to provide a specific utility to the user. A typical module reads one or more database tags, performs calculations by calling one or more models with the tag values, and writes the results to other database tags.


Parameter
    A configuration variable associated with a specific unit.


Plant
    The entirety of all assets/units in a system combined. A geothermal doublet would be considered a plant.


Project
    A saved combination of components, settings, and data for a plant or asset
    scope in GEMINI.


Tag
    A named numeric data item in the database. Each tag stores time-stamped
    measured or calculated values.


Unit
    Digital representation of an asset, i.e. the blocks in the diagram builder.