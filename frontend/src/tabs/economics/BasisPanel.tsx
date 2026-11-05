// The cost basis on the Economics tab, where the cost is shown: what the design's €/MWh includes
// and leaves out, the discount rate, lifetimes and prices, how heat and cold share the costs, and
// how far the cost moves with each assumption (GET /api/cost-basis: the same plant repriced by the
// real economics). The Assumptions drawer changes the prices; the basis follows them.

import { CostBasisView } from "../../components/CostBasis";
import { AskButton, ProvenanceChip, useResource, type Design, type Provenance } from "../../workbench";
import { getCostBasis } from "../../workbench/basis";
import { Panel } from "../energy/parts";
import { eur } from "./format";

export function BasisPanel({ design, threadId, prov, delay }: { design: Design; threadId: string | null; prov: Provenance; delay?: number }) {
  const e = design.economics;
  // Refetched when the design or its cost changes (the drawer's Apply reprices it).
  const basis = useResource((signal) => getCostBasis(threadId ?? "", design.id, signal), [threadId, design.id, e.lcoe, e.lcoh, e.lcoc]);
  if (!threadId || basis.status === "error" || (!basis.data && basis.status !== "loading")) return null;
  const head = e.lcoe ?? e.lcoh;
  return (
    <Panel
      title="Cost basis"
      sub={`What the ${eur(head)} €/MWh of heat and cold includes and leaves out, on which terms, and how far it moves`}
      delay={delay}
      className="ec-basis"
      aside={
        <>
          <ProvenanceChip source={prov} detail="Each swing reprices this same plant with one assumption changed (Dioscuri's economics)" />
          <AskButton compact label="Ask about the cost basis" context={`${design.code}'s cost basis on the Economics tab`} question="What is left out of the cost of heat and cold, and why?" />
        </>
      }
    >
      {basis.data ? <CostBasisView basis={basis.data} /> : <p className="ee-foot">Working out how far the cost moves…</p>}
    </Panel>
  );
}
