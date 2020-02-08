// for the web page
export { DomBind } from "@polymer/polymer/lib/elements/dom-bind.js";
export { StreamedGraph } from "streamed-graph";

import { LitElement, property, html, customElement } from "lit-element";

import { Literal, N3Store } from "n3";
import { NamedNode, DataFactory } from "n3";
const { namedNode, literal } = DataFactory;

import { VersionedGraph } from "streamed-graph";
// import style from "./style.styl";
import { labelFromUri, graphLiteral, graphUriValue } from "./graph_access";

const room = "http://projects.bigasterisk.com/room/";

function asString(x: Literal | undefined): string {
  if (x && x.value) {
    return x.value;
  }
  return "(unknown)";
}

@customElement("mqtt-to-rdf-page")
export class MqttToRdfPage extends LitElement {
  // static get styles() {
  //   return [style];
  // }

  @property({ type: Object })
  graph!: VersionedGraph;

  connectedCallback() {
    super.connectedCallback();
    const sg = this.ownerDocument!.querySelector("streamed-graph");
    sg?.addEventListener("graph-changed", ((ev: CustomEvent) => {
      this.graph = ev.detail!.value as VersionedGraph;
    }) as EventListener);
  }

  static get observers() {
    return ["onGraphChanged(graph)"];
  }

  render() {

    return html`
      <pre>
       mqtt_to_rdf

      connected to <mqtt server>

      messages received <n from stats page>

      subscribed topics:
        ari nightlight temp: 72.2 <graph>
        ...


      </pre>
    `;
  }

}
