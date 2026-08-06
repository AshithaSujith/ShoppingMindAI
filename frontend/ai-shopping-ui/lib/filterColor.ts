import { FILTERCOLORS } from "./constants";

export function filterColor(index: number) {
  return FILTERCOLORS[index % FILTERCOLORS.length];
}