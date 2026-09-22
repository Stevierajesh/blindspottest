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

With this we can start to build a model of the application, in graph form.

So maybe something like this:

```bash
Projects page
→ "New Project"
→ form with Name field
→ "Create"
→ Project Details page
```

The AI can ask, which of the preloaded behavior patterns does this match? 

and we can have a list of possible labels, like:

```bash
CREATE_RESOURCE
UPDATE_RESOURCE
DELETE_RESOURCE
PERSISTENT_MUTATION
SORT_COLLECTION
FILTER_COLLECTION
AUTHENTICATE
SEARCH
UNKNOWN
```

and from there, we can have the knowledge engine verify that it's the correct invariant for the flow, and then generate the test.