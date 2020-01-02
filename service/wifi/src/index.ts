import { PolymerElement, html } from "@polymer/polymer";
import {
  customElement,
  property,
  computed,
  observe,
} from "@polymer/decorators";
import { N3Store } from "n3";
//import {* as wt} from './wifi-table';
import { VersionedGraph, StreamedGraph } from "streamed-graph";
export { DomBind } from "@polymer/polymer/lib/elements/dom-bind.js";

console.log("here is a real dependency on ", StreamedGraph.name);

@customElement("wifi-display")
class WifiDisplay extends PolymerElement {
  @property({ type: Object, observer: WifiDisplay.prototype.onGraphChanged})
  graph!: VersionedGraph;


  onGraphChanged() {
    console.log("new graph", this.graph);
  }

  ready() {
    super.ready();
  }

  // redraw() {
  //     wt.render(this.graph.graph);
  // }
  static get template() {
    return html`
      here
    `;
  }
}
