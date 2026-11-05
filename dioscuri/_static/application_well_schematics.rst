Well Schematics
===============

Description
---------------------------
Comprehensive tool for creating, visualizing, and managing detailed well
schematic diagrams used in integrity workflows.

Schematics components
---------------------------
Each unit is configured through tabs: **General**, **Caprock**, **Tubulars**,
**Fluids**, **Cements**, **Packers**, **Plugs**, **Screens**, **Wellhead**, and
**Xmas Tree**.

General (layout and figure)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Layout Mode:** Uniform | Depth Transformed (Uniform: fixed width; Depth Transformed: scale by depth).
  * **Uniform Width** — Tubular width.
  * **Uniform Spacing** — Annular space.
  * **Figure Size Width** — Figure width.
  * **Figure Size Height** — Figure height.
  * **Show Axes** — When unchecked, hides axis labels, ticks, spines, and grid.

Caprock
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Caprock** — Optional caprock band drawn over a depth interval.

  **Options:** Enable Caprock. Top Depth [m]; Bottom Depth [m]; Hatch Pattern: ``--`` | ``//``.

Tubulars
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Casing** — Pipe cemented in the wellbore (conductor, surface, intermediate); can be tapered. Defines top/bottom depth, OD/ID, and optional openhole.
  * **Tubing** — Production conduit inside casing; can include an ESP interval.
  * **Liner** — Casing that does not extend to surface. Same depth/OD/ID as other tubulars.

  **Options:** Type: Casing | Tubing | Liner. Top/Bottom Depth [m]; Inner Diameter [inch]; Outer Diameter [inch]; optional Openhole Diameter [inch] with optional Hole Top Depth / Hole Bottom Depth [m]. Draw Shoe toggle. Number of hanger seals per spool: 1 | 2. Casing can be tapered (define one or more depth segments with Top/Bottom [m] and ID/OD [inch]). Tubing can enable an ESP interval (ESP Top/Bottom Depth [m]).

Fluids
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Inner fluids** — Fluids inside a tubular. Defined by type, location, and depth interval (top–bottom).
  * **Annulus fluids** — Fluids in the ring between two tubulars; use location “Outside”.

  **Options:** Fluid type: Brine | Oil | Mud | Gas | Water | Air | N2 | Empty. Location: Inside | Outside. Top/Bottom Depth [m]; optional Density.

Cements
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Cement** — Cement in the wellbore (inside or outside a tubular). Defined by type, location, and depth interval.

  **Options:** Cement type: Standard | Foamed | Lightweight | Ultra-Lightweight. Location: Inside | Outside.

Packers
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Packer** — Seals the annulus at a depth interval. Placed within a tubular unit.

  **Options:** Packer type: Primary | Standard | Mechanical | Retrievable | Permanent | Inflatable | Hydraulic | Compression | Tension.

Plugs
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Plug** — Blocks the bore at a depth. Placed within a tubular unit.

  **Options:** Plug type: Cement | Bridge | Mechanical.

Screens
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Screen** — Completion screen over a depth interval (e.g. for sand control). Placed within a tubular unit.

  **Options:** Screen type: Wire Wrap | Slotted | Perforated | Mesh.

Wellhead
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Enable Wellhead Valves** — Toggle to show/hide wellhead valves on the schematic.
  * **Show Seals** — Toggle wellhead seals. The seal layout is derived from the tubular ``num_seals`` and annulus geometry.
  * **Per-spool configuration** — Collapsible advanced section for A-annulus, B-Ring, C-Ring, and D-Ring. For each: Enable; Include Left Valves; Include Right Valves. Controls which annulus valves are drawn at the wellhead.

Xmas Tree
~~~~~~~~~~~~~~~~~~~~~~~~~~~
  * **Enable X-mas Tree** — Toggle to show/hide the Christmas tree on the schematic.
  * **Options:** Lower Master Valve | Upper Master Valve | Swab Valve | Wing Valves | Left Wing Valve | Right Wing Valve. Each can be included or excluded in the drawn tree.

Workflow (per Well Schematics app)
------------------------------------
The toolbar at the top of the app holds the **Well** dropdown, the **Schematic**
dropdown, a status badge, and the **New**, **Save**, **Save As…**, and **Delete**
buttons.

1. **Select well** — Choose a well from the **Well** dropdown (well list is loaded from the project).

        .. image:: images/application_schematics_1.png
            :width: 100%
            :align: center

2. **Create or load a schematic**
   * **Create new** — Click **New** (or choose *New schematic* in the **Schematic** dropdown) to open the template picker. Choose a template — Simple Well, Standard Well, Double Skin, or Create from Scratch — and the editor opens with template data or empty.
   * **Load existing** — Select a saved schematic in the **Schematic** dropdown; it loads automatically into the editor. If the current schematic has unsaved changes, you are prompted to save or discard before switching.

        .. image:: images/application_schematics_2.png
          :width: 100%
          :align: center

3. **Define units**
   * **Add unit** — In the **Current Units** panel click **Add unit**, then fill the tabs: **Tubulars** (type, name, depths, OD/ID, optional openhole and hole interval, draw shoe, hanger seals; for tubing, optional ESP), plus **Fluids**, **Cements**, **Packers**, **Plugs**, and **Screens**. Set **General** (layout, figure size, show axes), **Caprock**, **Wellhead**, and **Xmas Tree** as needed.
   * **Edit unit** — Select a unit in the **Current Units** list to edit it in the tabs. Edits are held in the working schematic and are persisted when you save; there is no separate per-unit save.

          .. image:: images/application_schematics_3.png
            :width: 100%
            :align: center

4. **Preview** — Click **Generate Schematic** in the schematic output card to draw the diagram.

5. **Save schematic** — Click **Save** to store changes, or **Save As...** to
   save under a new name. Use **Delete** to remove the selected schematic.
   Schematics are stored on the server for the selected well.




      








