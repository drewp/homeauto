import { Literal, N3Store, Util, NamedNode, DataFactory } from "n3";
const { literal, namedNode } = DataFactory;

// workaround for uris that don't have good labels in the graph
export function labelFromUri(
  uri: NamedNode,
  prefix: string,
  tailsToLabels: { [key: string]: string },
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

export function graphLiteral(
  store: N3Store,
  subj: NamedNode,
  pred: string,
  notFoundResult?: string
): Literal {
  const keep: Array<Literal> = [];
  store.forEach(
    q => {
      if (!Util.isLiteral(q.object)) {
        throw new Error("non literal found");
      }
      let seen = false;
      for (let other of keep) {
        // why are we getting multiple matches for the same literal? seems like a bug
        if (other.equals(q.object)) {
          seen = true;
        }
      }
      if (!seen) {
        keep.push(q.object as Literal);
      }
    },
    subj,
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
  console.log(`${subj.value} ${pred} had ${keep.length} objects:`, keep);
  return keep[0];
}

export function graphUriValue(
  store: N3Store,
  subj: NamedNode,
  pred: string
): NamedNode | undefined {
  const keep: Array<NamedNode> = [];
  store.forEach(
    q => {
      if (!Util.isNamedNode(q.object)) {
        throw new Error("non uri found");
      }
      keep.push(q.object as NamedNode);
    },
    subj,
    namedNode(pred),
    null,
    null
  );
  if (keep.length == 0) {
    return undefined;
  }
  if (keep.length == 1) {
    return keep[0];
  }
  throw new Error("found multiple matches for pred");
}
