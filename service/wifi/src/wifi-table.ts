import { html } from 'lit-html';
import { NamedNode, DataFactory } from 'n3';
const { literal, quad, namedNode } = DataFactory;
import * as sgmod from 'streamed-graph';
import { Literal, Term, N3Store } from 'n3';

interface DevGroup {
  connectedToAp: NamedNode,
  wifiBand: NamedNode,
  devs: Array<Dev>
}
interface Dev {
  agoMin: number,
  ipAddress: Literal,
  dhcpHostname: string,
  macAddress: Literal,
  packetsPerSec: number,
  bytesPerSec: number
}

console.log('got', sgmod);

const NS: any = {
  room: 'http://projects.bigasterisk.com/room/'
}

// from rdf-uri.html
const BigastUri = {
  // not well defined for uri prefixes that are string prefixes of each other
  compactUri: function (uri: string) {
    if (uri === undefined) {
      return uri;
    }
    if (typeof (uri) == "object") { throw new Error("type"); }
    if (uri == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type") {
      return "a";
    }
    for (var short of Object.keys(NS as any)) {
      var prefix = NS[short];
      if (uri.indexOf(prefix) == 0) {
        return short + ':' + uri.substr(prefix.length);
      }
    }
    return uri;
  },
  expandUri: function (s: string) {
    for (var short of Object.keys(NS)) {
      var prefix = NS[short];
      if (s.indexOf(short + ":") == 0) {
        return prefix + s.substr(short.length + 1);
      }
    }
    return s;
  },
};

// workaround for uris that don't have good labels in the graph
function labelFromUri(uri: NamedNode, prefix: string, tailsToLabels: any, defaultLabel: string) {
  let label = defaultLabel === undefined ? uri.value : defaultLabel;
  Object.entries(tailsToLabels).forEach(([tail, useLabel]) => {
    if (uri.equals(namedNode(prefix + tail))) {
      label = useLabel as string;
    }
  });
  return label
}

// set out[suffix] = graph.get(subj, predPrefix+suffix) for all suffixes
function getProperties(store: N3Store, out: any, subject: Term, predPrefix: string, predSuffixes: Array<string>) {
  predSuffixes.forEach((term) => {
    store.forEach((q) => {
      out[term] = q.object;
    }, subject, namedNode(predPrefix + term), null, null);

    return out;
  });
}

function graphView(store: N3Store, showGroups: boolean): void {
  const grouped: Map<string, DevGroup> = new Map();
  store.forEach((q) => {
    const row: any = { uri: q.subject };

    getProperties(store, row, row.uri, 'room:',
      ['dhcpHostname', 'ipAddress', 'macAddress', 'connectedToAp', 'wifiBand', 'connected', 'bytesPerSec', 'packetsPerSec']);
    if (row.dhcpHostname && row.dhcpHostname.value) {
      row.dhcpHostname = row.dhcpHostname.value;
    }
    if (!showGroups || row.connectedToAp) {
      const key = (showGroups ? `${row.connectedToAp.toNT()}-${row.wifiBand.toNT()}` : 'all');
      if (!grouped.has(key)) {
        grouped.set(key, { connectedToAp: row.connectedToAp, wifiBand: row.wifiBand, devs: [] });
      }
      grouped.get(key)!.devs.push(row);
    } else {
      console.log('lost row', row);
    }
    if (row.connected) {
      const t = new Date(row.connected.value);
      const agoMs = (Date.now() as number) - (t as unknown as number);
      row.agoMin = agoMs / 1000 / 60;
    }
    if (row.bytesPerSec) { row.bytesPerSec = row.bytesPerSec.valueOf() + ' B/s'; }
    if (row.packetsPerSec) { row.packetsPerSec = row.packetsPerSec.valueOf() + ' p/s'; }
  }, null, namedNode('rdf:type'), namedNode('room:NetworkedDevice'), null);
}

const renderDevice = (dev: Dev) => {
  const glow = Math.max(0, 1 - dev.agoMin / 60);
  const agoReport = dev.agoMin < 360 ? ` (${Math.ceil(dev.agoMin * 10) / 10} minutes ago)` : '';
  return html`
      <div class="dev" style="background: rgba(185, 5, 138, ${glow});">
        <span class="mac">${dev.macAddress.value}</span>
        <span class="ip"><a href="http://${dev.ipAddress.value}/">${dev.ipAddress.value}</a></span>
        <span class="packets">${dev.packetsPerSec}</span>
        <span class="bytes">${dev.bytesPerSec}</span>
        <span class="hostname">${dev.dhcpHostname}</span>
        <span class="ago">${agoReport}</span>
        <span class="links">
          <a href="https://bigasterisk.com/ntop/lua/host_details.lua?ifid=17&amp;host=${dev.ipAddress.value}&amp;page=flows">[flows]</a>
        </span>
      </div>
    `;
};

const renderGroup = (key: string, group: DevGroup) => {
  let label;
  if (key != 'all') {
    label = labelFromUri(group.connectedToAp,
      'http://bigasterisk.com/mac/',
      {
        'a0:40:a0:6f:96:d5': "Main router (d5)",
        '8c:3b:ad:c4:8d:ce': "Downstairs satellite (ce)",
        'a0:40:a0:6f:aa:f8': "Upstairs satellite (f8)",
      },
      "unknown");

    label += labelFromUri(group.wifiBand,
      'http://projects.bigasterisk.com/room/wifiBand/',
      {
        '5G': ' 5G',
        '2.4G': ' 2.4G',
      },
      "unknown");
  }

  const devs = group.devs;
  function padIp(ip: string) { return ip.replace(/(\d+)/g, (m) => ('00' + m).slice(-3)); }
  devs.sort((a, b) => { return padIp(a.ipAddress.value) > padIp(b.ipAddress.value) ? 1 : -1; });
  return html`
      <tr>
        <th>${label}</th>
        <td>
          <div>Devices:</div>
          ${devs.map((d) => { return renderDevice(d); })}
        </td>
      </tr>
      `;
  /*
let groups=['?'];
const out = html`
<style>

  .report { font-family: sans-serif; }
  section { margin-left: 1em; }
  .dev { margin-bottom: 2px; }
  .ip, .mac, .packets, .bytes {
      display: inline-block;
      font-family: monospace;
  }
  .packets, .bytes {
      text-align: right;
      padding-right: 1em;
  }
  .mac     {color: #ccffcc; width: 11em; }
  .ip      {color: #b5b5d4; width: 6em; }
  .packets {color: #2da1a5; width: 6em; }
  .bytes   {color: #a5912d; width: 9em; }
  th,td { vertical-align: top; }
  th { background: #333; }
  td { background: #252525; }

</style>
<div class="report">
  report
  <table>
    ${groups.map((row) => { return renderGroup(row[0], row[1]); })}
  </table>
</div>
`;
return out;*/
}
export { graphView }
