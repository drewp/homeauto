
This is https://github.com/juggernaut/twisted-sse-demo with some
changes, including:

- rename from twisted-sse-demo to twisted_sse so it can be a package
- add setup.py so it can be depended on
- some python3 support
- remove crochet

api_example.py is probably out of date.

drewp is using cyclone.sse for server support and this
twisted_sse.eventsource as the client.
