console.log('p-1');
import { PolymerElement, html } from '@polymer/polymer';
import { customElement, property, computed } from '@polymer/decorators';
import { N3Store } from "n3"
//import {* as wt} from './wifi-table';
import { VersionedGraph, StreamedGraph } from "streamed-graph";
export {DomBind} from '@polymer/polymer/lib/elements/dom-bind.js';
console.log('p0');
console.log('p1', StreamedGraph.name);
@customElement('wifi-display')
class WifiDisplay extends PolymerElement {

    @property({ type: Object })
    graph!: StreamedGraph;

    ready() {
        super.ready();
        console.log('p2');
        // this.graph.addEventListener('change', this.redraw.bind(this));
    }
    // redraw() {
    //     wt.render(this.graph.graph);
    // }
    static get template() {
        return html`here`;
    }
}
console.log('p3');