// for the web page
export { DomBind } from "@polymer/polymer/lib/elements/dom-bind.js";
export { StreamedGraph } from "streamed-graph";

import { LitElement, property, html, customElement } from "lit-element";

import { Literal, N3Store } from "n3";
import { NamedNode, DataFactory } from "n3";
const { namedNode } = DataFactory;

import { VersionedGraph } from "streamed-graph";
import { style } from "./style";
import { labelFromUri, graphLiteral, graphUriValue } from "./graph_access";

interface DevGroup {
  connectedToAp: NamedNode;
  wifiBand: NamedNode;
  devs: Array<Dev>;
}
interface Dev {
  agoMin: number | undefined;
  ipAddress: Literal; // todo no one wants this literal. just make it string.
  dhcpHostname: string;
  macAddress: Literal;
  packetsPerSec: number;
  packetsPerSecDisplay: string;
  bytesPerSec: number;
  bytesPerSecDisplay: string;
}
const room = "http://projects.bigasterisk.com/room/";

function asString(x: Literal | undefined): string {
  if (x && x.value) {
    return x.value;
  }
  return "(unknown)";
}

@customElement("wifi-display")
class WifiDisplay extends LitElement {
  static get styles() {
    return [style];
  }

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

  @property({ type: Boolean })
  showGroups = false;

  render() {
    const grouped = this.graphView(this.graph.store!);

    return html`
      <div class="report">
        <table>
          ${Array.from(grouped.entries()).map((row: [string, DevGroup]) => {
            return this.renderGroup(row[0], row[1]);
          })}
        </table>
      </div>
    `;
  }

  renderDevice(dev: Dev) {
    let agoReport = "";
    let glow = 0;
    if (dev.agoMin === undefined) {
      agoReport = "unknown";
    } else {
      glow = Math.max(0, 1 - dev.agoMin! / 60);
      agoReport =
        dev.agoMin! < 360
          ? ` (${Math.ceil(dev.agoMin! * 10) / 10} minutes ago)`
          : "";
    }
    const ntopUrl = "https://bigasterisk.com/ntop/lua/host_details.lua";
    const ntopLink = `${ntopUrl}?ifid=17&amp;host=${dev.ipAddress.value}&amp;page=flows`;
    return html`
      <div class="dev" style="background: rgba(185, 5, 138, ${glow});">
        <span class="mac">${dev.macAddress.value}</span>
        <span class="ip"
          ><a href="http://${dev.ipAddress.value}/"
            >${dev.ipAddress.value}</a
          ></span
        >
        <span class="packets">${dev.packetsPerSecDisplay}</span>
        <span class="bytes">${dev.bytesPerSecDisplay}</span>
        <span class="hostname">${dev.dhcpHostname}</span>
        <span class="ago">${agoReport}</span>
        <span class="links"><a href="${ntopLink}">[flows]</a></span>
      </div>
    `;
  }

  renderGroup(key: string, group: DevGroup) {
    let label;
    if (key != "all") {
      label = labelFromUri(
        group.connectedToAp,
        "http://bigasterisk.com/mac/",
        {
          "a0:40:a0:6f:96:d5": "Main router (d5)",
          "8c:3b:ad:c4:8d:ce": "Downstairs satellite (ce)",
          "a0:40:a0:6f:aa:f8": "Upstairs satellite (f8)",
        },
        "unknown"
      );

      label += labelFromUri(
        group.wifiBand,
        "http://projects.bigasterisk.com/room/wifiBand/",
        {
          "5G": " 5G",
          "2.4G": " 2.4G",
        },
        "unknown"
      );
    }

    const devs = group.devs;
    function padIp(ip: string) {
      return ip.replace(/(\d+)/g, m => ("00" + m).slice(-3));
    }
    devs.sort((a, b) => {
      return padIp(a.ipAddress.value) > padIp(b.ipAddress.value) ? 1 : -1;
    });
    return html`
      <tr>
        <th>${label}</th>
        <td>
          <div>Devices:</div>
          ${devs.map(d => {
            return this.renderDevice(d);
          })}
        </td>
      </tr>
    `;
  }

  addGroupedDev(
    store: N3Store,
    grouped: Map<string, DevGroup>,
    devUri: NamedNode
  ) {
    const getAgoMin = (connected: Literal | undefined): number | undefined => {
      if (connected) {
        const t = new Date(connected.value);
        const agoMs = Date.now() - t.valueOf();
        return agoMs / 1000 / 60;
      }
      return undefined;
    };

    const packetsPerSec = parseFloat(
      graphLiteral(store, devUri, room + "packetsPerSec", "0").value
    );
    const bytesPerSec = parseFloat(
      graphLiteral(store, devUri, room + "bytesPerSec", "0").value
    );

    const row: Dev = {
      agoMin: getAgoMin(graphLiteral(store, devUri, room + "connected")),
      ipAddress: graphLiteral(store, devUri, room + "ipAddress", "(unknown)"),
      dhcpHostname: asString(
        graphLiteral(store, devUri, room + "dhcpHostname")
      ),
      macAddress: graphLiteral(store, devUri, room + "macAddress"),
      packetsPerSec: packetsPerSec,
      packetsPerSecDisplay: packetsPerSec + " P/s",
      bytesPerSec: bytesPerSec,
      bytesPerSecDisplay: bytesPerSec + " B/s",
    };

    const wifiBand = graphUriValue(store, devUri, room + "wifiBand");
    const connectedToAp = graphUriValue(store, devUri, room + "connectedToAp");
    if (!this.showGroups || connectedToAp) {
      const key = this.showGroups
        ? `${connectedToAp!.value}-${wifiBand!.value}`
        : "all";
      if (!grouped.has(key)) {
        grouped.set(key, {
          connectedToAp: connectedToAp!,
          wifiBand: wifiBand!,
          devs: [],
        });
      }
      grouped.get(key)!.devs.push(row);
    } else {
      console.log("row didn't get into any group:", row);
    }
  }

  graphView(store: N3Store): Map<string, DevGroup> {
    const grouped: Map<string, DevGroup> = new Map();
    store.forEach(
      q => {
        const devUri: NamedNode = q.subject as NamedNode;
        this.addGroupedDev(store, grouped, devUri);
      },
      null,
      namedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
      namedNode(room + "NetworkedDevice"),
      null
    );
    return grouped;
  }
}
