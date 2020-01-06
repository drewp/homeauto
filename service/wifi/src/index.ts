// for the web page
export { DomBind } from "@polymer/polymer/lib/elements/dom-bind.js";

import { LitElement, property, html, customElement } from "lit-element";

import { Literal, Term, N3Store, Util } from "n3";
import { NamedNode, DataFactory } from "n3";
const { literal, quad, namedNode } = DataFactory;

import { VersionedGraph } from "streamed-graph";
export { StreamedGraph } from "streamed-graph";
import { style } from "./style";

interface DevGroup {
  connectedToAp: NamedNode;
  wifiBand: NamedNode;
  devs: Array<Dev>;
}
interface Dev {
  agoMin: number | undefined;
  ipAddress: Literal;
  dhcpHostname: string;
  macAddress: Literal;
  packetsPerSec: string; //number; todo
  bytesPerSec: string; //number;
}

// workaround for uris that don't have good labels in the graph
function labelFromUri(
  uri: NamedNode,
  prefix: string,
  tailsToLabels: any,
  defaultLabel: string
) {
  let label = defaultLabel === undefined ? uri.value : defaultLabel;
  Object.entries(tailsToLabels).forEach(([tail, useLabel]) => {
    if (uri.equals(namedNode(prefix + tail))) {
      label = useLabel as string;
    }
  });
  return label;
}

@customElement("wifi-display")
class WifiDisplay extends LitElement {
  static get styles() {
    return [style];
  }

  @property({
    type: Object,
    //    observer: WifiDisplay.prototype.onGraphChanged,
  })
  graph!: VersionedGraph;

  connectedCallback() {
    super.connectedCallback();
    console.log("wifidisplay connected");
    const sg = this.ownerDocument!.querySelector("streamed-graph");
    sg?.addEventListener("graph-changed", ((ev: CustomEvent) => {
      this.graph = ev.detail!.value as VersionedGraph;
      console.log("wifidisplay got new graph", this.graph);
    }) as EventListener);
  }

  static get observers() {
    return ["onGraphChanged(graph)"];
  }

  @property({ type: Object }) //no longer a prop?
  grouped: Map<string, DevGroup> = new Map();

  render() {
    const grouped = this.graphView(this.graph.store!, false);

    return html`
      <div class="report">
        report at graph version ${this.graph.version} grouped:
        ${Array.from(grouped.entries()).length}
        <table>
          ${Array.from(grouped.entries()).map((row: [string, DevGroup]) => {
            return this.renderGroup(row[0], row[1]);
          })}
        </table>
      </div>
    `;
  }

  onGraphChanged(val: VersionedGraph, old: VersionedGraph) {
    console.log("new graph value", this.graph);
    this.grouped = this.graphView((val as VersionedGraph).store!, false);
  }

  renderDevice(dev: Dev) {
    let agoReport = "";
    if (dev.agoMin === undefined) {
      agoReport = "unknown";
    } else {
      const glow = Math.max(0, 1 - dev.agoMin! / 60);
      agoReport =
        dev.agoMin! < 360
          ? ` (${Math.ceil(dev.agoMin! * 10) / 10} minutes ago)`
          : "";
    }
    const glow = ""; //todo
    return html`
      <div class="dev" style="background: rgba(185, 5, 138, ${glow});">
        <span class="mac">${dev.macAddress && dev.macAddress.value}</span>
        <span class="ip"
          ><a href="http://${dev.ipAddress && dev.ipAddress.value}/"
            >${dev.ipAddress && dev.ipAddress.value}</a
          ></span
        >
        <span class="packets">${dev.packetsPerSec}</span>
        <span class="bytes">${dev.bytesPerSec}</span>
        <span class="hostname">${dev.dhcpHostname}</span>
        <span class="ago">${agoReport}</span>
        <span class="links">
          <a
            href="https://bigasterisk.com/ntop/lua/host_details.lua?ifid=17&amp;host=${dev.ipAddress &&
              dev.ipAddress.value}&amp;page=flows"
            >[flows]</a
          >
        </span>
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
      return 0; //todo
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

  graphView(store: N3Store, showGroups: boolean): Map<string, DevGroup> {
    const grouped: Map<string, DevGroup> = new Map();
    const room = "http://projects.bigasterisk.com/room/";
    store.forEach(
      q => {
        const devUri: NamedNode = q.subject as NamedNode;

        const graphLiteral = (
          store: N3Store,
          devUri: NamedNode,
          pred: string,
          notFoundResult?: string
        ): Literal => {
          const keep: Array<Literal> = [];
          store.forEach(
            q => {
              if (!Util.isLiteral(q.object)) {
                throw new Error("non literal found");
              }
              keep.push(q.object as Literal);
            },
            devUri,
            namedNode(pred),
            null,
            null
          );
          if (keep.length == 0) {
            return literal(notFoundResult || "(missing)");
          }
          if (keep.length == 1) {
            return keep[0];
          }
          throw new Error("found multiple matches for pred");
        };

        const getAgoMin = (
          connected: Literal | undefined
        ): number | undefined => {
          if (connected) {
            const t = new Date(connected.value);
            const agoMs = Date.now() - t.valueOf();
            return agoMs / 1000 / 60;
          }
          return undefined;
        };

        const asString = (x: Literal | undefined): string => {
          if (x && x.value) {
            return x.value;
          }
          return "(unknown)";
        };
        const row: Dev = {
          agoMin: getAgoMin(
            literal("2020-01-01") //  graphLiteral(store, devUri, room + "connectedToAp")
          ),
          ipAddress: graphLiteral(
            store,
            devUri,
            room + "ipAddress",
            "(unknown)"
          ),
          dhcpHostname: asString(
            graphLiteral(store, devUri, room + "dhcpHostname")
          ),
          macAddress: graphLiteral(store, devUri, room + "macAddress"),
          packetsPerSec:
            graphLiteral(store, devUri, room + "packetsPerSec", "? ").value +
            " P/s", //number; todo
          bytesPerSec:
            graphLiteral(store, devUri, room + "bytesPerSec", "? ").value +
            "B/s", //number;
        };
        if (row.dhcpHostname && (row.dhcpHostname as any).value) {
          row.dhcpHostname = (row.dhcpHostname as any).value;
        }
        if (!showGroups || (row as any).connectedToAp) {
          const key = showGroups
            ? `${(row as any).connectedToAp.toNT()}-${(row as any).wifiBand.toNT()}`
            : "all";
          if (!grouped.has(key)) {
            grouped.set(key, {
              connectedToAp: (row as any).connectedToAp,
              wifiBand: (row as any).wifiBand,
              devs: [],
            });
          }
          grouped.get(key)!.devs.push(row);
        } else {
          console.log("lost row", row);
        }

        if (row.bytesPerSec) {
          row.bytesPerSec = row.bytesPerSec.valueOf() + " B/s";
        }
        if (row.packetsPerSec) {
          row.packetsPerSec = row.packetsPerSec.valueOf() + " p/s";
        }
      },
      null,
      namedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
      namedNode(room + "NetworkedDevice"),
      null
    );
    return grouped;
  }
}
