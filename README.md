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

We can have the system learn new behaviour patterns and add them to invarients if needed.


and from there, we can have the knowledge engine verify that it's the correct invariant for the flow, and then generate the test instances to test on the runner.


## The demo application

Flow discovery needs flows to discover, so the demo is now a small but whole app
rather than three forms. `make run` serves it, `make pages` opens it.

```bash
/                    overview
/login  /account     sign in, contact details, sign out
/projects            list -> new -> detail -> edit -> delete
/catalog             search, category filter, sort
/cart                cart -> contact -> [upsell] -> shipping -> payment -> confirmation
/profile             the original persistence page
/project-settings    the same invariant in different words
```

The checkout is the one that makes the argument. The upsell step only appears
when the subtotal clears $150, so two runs of the *correct* application take two
different paths:

```bash
Cart -> Contact -> Shipping -> Payment -> Confirmation
Cart -> Contact -> Upsell -> Shipping -> Payment -> Confirmation
```

Both are valid. Nothing about the path is the specification — what has to hold is
that the confirmation lists what was in the cart and the total equals the sum of
the lines it shows.

### Two builds

The whole app is mounted twice from the same code:

```bash
/            sound
/broken/...  same app, one behaviour changed per flow
```

Same templates, same wording, same markup — so finding the defect is a testing
problem and not a reading-comprehension one. What is planted where:

| flow | defect |
|---|---|
| profile | Bio is never written; the page still says "Saved successfully" |
| account | sign out shows the confirmation but never clears the session |
| projects | delete is a soft delete: row disappears, resource still reachable, still counted |
| catalog | the price sort orders the rendered string, so $1,299.00 sorts before $89.00 |
| checkout | the protection plan is listed on the confirmation but left out of the total |

Only the first is a persistence bug. The other four are the kind the current MVP
structurally cannot see: they are conditions about a *flow's outcome* — something
no longer existing, an order between rows, a sum across lines — not about one
field surviving a reload.

### What the current pipeline does with it

`make broken` still works exactly as before — it finds the dropped Bio on a
single page. `make edit` points the same pipeline at the project edit form and
comes back **inconclusive**: the commit navigates to the detail page, so when the
runner reloads and goes looking for the field it was watching, the field isn't
there. Nothing is wrong with the application. The test is shaped like a page and
the behaviour is shaped like a flow, which is the gap to close.

### Ground truth

`make truth` (or `/__truth`) prints, per flow, the capability, the goal
conditions, the invariants, the paths a run may take, and the planted defect.
It is there so flow discovery can be scored against something instead of
eyeballed. Nothing in the app reads it, and no page links to it.

State is per browser session (a cookie) and the two builds keep separate copies,
so two scans never collide, and `POST /reset` puts a session back to the seed.