### How it works 

The page inspector simplifies the DOM, sends it to the classifier, in which AI will decide which elements to test, which sends it to the knowledge engine that will extract the property type and find the invarient (preloaded), it will then send the property type and invarient to the test generator, which will generate the test and send it to the test runner, which will run the test and send the result back to the knowledge engine, which will go to the reporter.


I am trying to see, instead of specific varients if we can do this with entire flows..


What that architecture looks like is a little blurry so here's my best try at it.

Current MVP architecture is centered on local invarients, more specifically for this test being persistance.

so an example of an invariant would be:

```bash
edit field
 -> save
 -> reload
 -> compare
```

Works well for distinct properties, but not for flows.

A purchase flow may well be 

```bash
Cart
 -> Checkout
 -> Payment
 -> Confirmation
```

but could later become 

```bash
Cart
→ Checkout
→ Upsell
→ Shipping
→ Payment
→ Confirmation
```

the second flow may be completely valid, so a requirement would be for blindspot to not *treat the exact path as the specification*.


The architecture needs to be able to distingush between:

```bash
Capability
Goal Conditions
Invariants
Observed Path
```





My next piece of work is to find a way to discover entirety of a flow.

1. Discovery
   What does the application currently expose?