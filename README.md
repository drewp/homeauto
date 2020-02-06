# Goals

Make rules easy to add and experiment with. 
Be transparent and debuggable. 
Don't pack things into names that need to be parsed out. 
Prefer RDF and URIs over ad-hoc structures and ids. 
Integrate with lots of outside data sources. 

## Input

Services create RDF graphs (legacy) and send MQTT messages (esp32 nodes, and eventually everything)

`mqtt_to_rdf` gathers those inputs; writes some of them to influxdb; turns them into an RDF graph

`collector` takes multiple RDF graphs and merges them into new combinations

## Reasoning
`reasoning` takes an RDF graph and N3 rules; emits an RDF graph (and makes HTTP PUT and POST requests)

## Output

`rdf_to_mqtt` takes RDF graph and emits MQTT messages

(`reasoning` does some of its own output actions)

Services (sometimes, the same ones that gathered input) perform home automation outputs.
