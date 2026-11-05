Parameters overview
===========================


Description
---------------------------
This application provides a consolidated view of component parameters and
tagnames for the active project plant model.

Overview of parameters and tagnames
-------------------------------------

Select an asset from the dropdown list. The list is populated from the current
project diagram. If no diagram exists, the dropdown remains empty.

.. image:: images/parameters_overview_dropdown_list.png
    :width: 50%

When an asset is selected, tables are updated automatically. If an asset has no
custom name, GEMINI generates one from asset type and the first four ID
characters.

.. image:: images/parameters_overview_parameters_table.png
    :width: 100%

The parameter table shows parameter names and editable values. For array-based
fields such as ``esp_head_coeff`` or ``esp_power_coeff``, separate values with
semicolons (``;``).

.. image:: images/parameters_overview_tagnames_table.png
    :width: 100%

The tagname table shows tag names, mapped values, and measured/calculated type.
Like parameters, these fields are editable.

Modify parameters
----------------------------
Use this page both to review and to update parameters/tags.

.. image:: images/parameters_overview_update_button.png
    :width: 20%

Click **Update** (bottom-left) to save changes. Save before switching to another
asset to prevent losing edits.
