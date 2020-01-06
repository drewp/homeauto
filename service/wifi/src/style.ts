import { css } from "lit-element";

export const style = css`
  .report {
    font-family: sans-serif;
  }
  section {
    margin-left: 1em;
  }
  .dev {
    margin-bottom: 2px;
  }
  .ip,
  .mac,
  .packets,
  .bytes {
    display: inline-block;
    font-family: monospace;
  }
  .packets,
  .bytes {
    text-align: right;
    padding-right: 1em;
  }
  .mac {
    color: #ccffcc;
    width: 11em;
  }
  .ip {
    color: #b5b5d4;
    width: 6em;
  }
  .packets {
    color: #2da1a5;
    width: 6em;
  }
  .bytes {
    color: #a5912d;
    width: 9em;
  }
  th,
  td {
    vertical-align: top;
  }
  th {
    background: #333;
  }
  td {
    background: #252525;
  }
`;
