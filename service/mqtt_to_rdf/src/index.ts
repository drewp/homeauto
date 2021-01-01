// for the web page
export { DomBind } from "@polymer/polymer/lib/elements/dom-bind.js";
// export { StreamedGraph } from "streamed-graph";

import {
  LitElement,
  property,
  html,
  customElement,
  unsafeCSS,
} from "lit-element";

// import { Literal, N3Store } from "n3";
// import { NamedNode, DataFactory } from "n3";
// const { namedNode, literal } = DataFactory;

// import { VersionedGraph } from "streamed-graph";
import style from "./style.styl";
// import { labelFromUri, graphLiteral, graphUriValue } from "./graph_access";

// const room = "http://projects.bigasterisk.com/room/";

// function asString(x: Literal | undefined): string {
//   if (x && x.value) {
//     return x.value;
//   }
//   return "(unknown)";
// }

interface Msg {
  t: number;
  msg: string;
}
interface GraphAtTime {
  t: number;
  n3: string;
}
interface Metric {
  name: string;
  labels: { [_: string]: string };
  value: string;
}
interface Subscribed {
  topic: string;
  recentMessages: Msg[];
  recentParsed: GraphAtTime[];
  recentConversions: GraphAtTime[];
  currentMetrics: Metric[];
  currentOutputGraph: GraphAtTime;
}
interface PageData {
  server: string;
  messagesSeen: number;
  subscribed: Subscribed[];
}

@customElement("mqtt-to-rdf-page")
export class MqttToRdfPage extends LitElement {
  static get styles() {
    return unsafeCSS(style);
  }

  // @property({ type: Object })
  // graph!: VersionedGraph;

  connectedCallback() {
    super.connectedCallback();
    const data = new EventSource("debugPageData");
    data.addEventListener("message", (ev: { data: string }) => {
      this.pageData = JSON.parse(ev.data) as PageData;
      console.log("data update");
    });
    //   const sg = this.ownerDocument!.querySelector("streamed-graph");
    //   sg?.addEventListener("graph-changed", ((ev: CustomEvent) => {
    //     this.graph = ev.detail!.value as VersionedGraph;
    //   }) as EventListener);
  }

  // static get observers() {
  //   return ["onGraphChanged(graph)"];
  // }

  @property({})
  pageData: PageData = {
    server: "loading...",
    messagesSeen: 0,
    subscribed: [
      {
        topic: "top1",
        recentMessages: [
          { t: 123456, msg: "one" },
          { t: 234567, msg: "two" },
        ],
        recentParsed: [{ t: 123, n3: ":a :b :c ." }],
        recentConversions: [],
        currentMetrics: [],
        currentOutputGraph: { t: 1, n3: "(n3)" },
      },
    ],
  };

  render() {
    const d = this.pageData;
    const now = Date.now() / 1000;
    const ago = (t: number) => html`${Math.round(now - t)}s ago`;
    const recentMsg = (m: Msg) => html` <div>${ago(m.t)} msg=${m.msg}</div> `;
    const topicItem = (t: Subscribed, index: number) =>
      html`<div class="topic" style="grid-column: 1; grid-row: ${index + 2}">
        ${t.topic} ${t.recentMessages.map(recentMsg)}
      </div>`;

    const parsedMessage = (g: GraphAtTime) =>
      html` <div class="graph">graph: ${g.n3}</div> `;
    const parsedMessages = (t: Subscribed, index: number) =>
      html`
        <div style="grid-column: 2; grid-row: ${index + 2}">
          topic=${t.topic} ${t.recentParsed.map(parsedMessage)}
        </div>
      `;

    const metric = (m: Metric) =>
      html`<div>
        metrix ${m.name} ${JSON.stringify(m.labels)} = ${m.value}
      </div>`;
    const conversions = (t: Subscribed, index: number) =>
      html`
        <div style="grid-column: 3; grid-row: ${index + 2}">
          topic=${t.topic} ${t.recentConversions.map(parsedMessage)}
        </div>
      `;
    const outputMetrics = (t: Subscribed, index: number) =>
      html`
        <div style="grid-column: 4; grid-row: ${index + 2}">
          topic=${t.topic} ${t.currentMetrics.map(metric)}
        </div>
      `;
    const outputGraph = (t: Subscribed, index: number) =>
      html`
        <div style="grid-column: 5; grid-row: ${index + 2}">
          topic=${t.topic} ${parsedMessage(t.currentOutputGraph)}
        </div>
      `;
    return html`
      <h1>mqtt_to_rdf</h1>

      <section>connected to ${d.server}; messages received ${
      d.messagesSeen
    }</section>

      <div class="grid">
        <div class="hd" style="grid-row: 1; grid-column: 1">subscribed topics</div>
        ${d.subscribed.map(topicItem)}

        <div class="hd" style="grid-row: 1; grid-column: 2">parsed message: rx stream of Graph</div>
        ${d.subscribed.map(parsedMessages)}

        <div class="hd" style="grid-row: 1; grid-column: 3">conversions: rx stream (possible separate times from the previous) of Callable[[Graph], Graph]</div>
        ${d.subscribed.map(conversions)}

        <div class="hd" style="grid-row: 1; grid-column: 4">output metrics: prom collection according to converted graph</div>
        ${d.subscribed.map(outputMetrics)}

        <div class="hd" style="grid-row: 1; grid-column: 5">output graph: PatchableGraph</div>
        ${d.subscribed.map(outputGraph)}
      </section>
    `;
  }
}
