// The context menus, from one place: {...menuProps(target)} on what can be right-clicked, a
// <MenuButton> "⋯" beside it, and the host mounted once in main.tsx.

export { ContextMenuHost, MenuButton, menuProps, openMenuAt, type MenuHandlers, type TargetArg } from "./ContextMenu";
export { editFieldOf, costItemsFor, priceKeyOf, sensParamOfCost, seriesOfUnit } from "./domain";
export { useIntent, type Intents } from "./intent";
export { isMenuKey } from "./keys";
export { CHAT_HINT, menuFor } from "./registry";
export { answerTarget } from "./targets";
export type { DesignRef, MenuTarget } from "./types";
