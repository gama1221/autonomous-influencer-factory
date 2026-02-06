┌─────────────────────────────────┐
│         Observable Source       │
│  • YouTube Trends API           │
│  • TikTok Hashtag Stream        │
│  • Twitter Topic API            │
└───────────────┬─────────────────┘
                │ (notifies on change)
    ┌───────────┼───────────┐
    │           │           │
┌───▼───┐ ┌────▼────┐ ┌────▼────┐
│Trend  │ │Sentiment│ │Engagement│
│Observer│ │Observer │ │ Observer│
└────┬───┘ └────┬────┘ └────┬────┘
     │           │           │
     └───────────┼───────────┘
           ┌─────▼─────┐
           │  Reactor  │
           │  Agents   │
           └───────────┘


     ┌─────────────────────┐
     │     Agent Mediator  │
     │  • Coordinates      │
     │  • Resolves Conflicts│
     │  • Manages State    │
     └─────────┬───────────┘
        ┌──────┼──────┐
        │      │      │
    ┌───▼──┐┌─▼───┐┌─▼───┐
    │Research││Content││Quality│
    │ Agent  ││ Agent ││ Agent │
    └───────┘└──────┘└──────┘
        │       │       │
        └───────┼───────┘
          (don't communicate directly)