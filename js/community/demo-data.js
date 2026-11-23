/* Sample families for the preview. The site does not load docs/community/sample-data.json. */
window.SS_DEMO = {
  settings: {
    inviteRequired: true,
    inviteCode: "FRIENDS-TEST",
    nameCheck: true,
    addressCheck: true,
    harshLanguageCheck: true,
    harshWords: ["stupid", "idiot"],
    newAccountHoldCount: 2,
    flagsToHide: 3,
    trustedBadgeAfter: 3,
    lookingForExpireDays: 90,
    portalMonthlyFeeCents: null,
    portalDuesCutPercent: null,
    paymentsMode: "test-only",
    modules: {
      reviews: true, claims: true, groupPortal: true, lawGuides: true,
      lookingFor: true, events: true, badges: true, favorites: true
    },
    ratingCategories: [
      { id: "welcoming", label: "Welcoming to new families", active: true },
      { id: "organized", label: "Well organized", active: true },
      { id: "communication", label: "Clear communication", active: true },
      { id: "worth-it", label: "Worth the time and cost", active: true }
    ]
  },
  accounts: [
    { id: "acc_family_chen", email: "chen.family@example.com", password: "preview", emailVerified: true, displayName: "The Chen family", roles: ["family"], approvedReviewCount: 3, createdAt: "2026-11-01T15:00:00Z" },
    { id: "acc_family_new", email: "new.parent@example.com", password: "preview", emailVerified: true, displayName: "Alex P.", roles: ["family"], approvedReviewCount: 0, createdAt: "2026-11-22T18:00:00Z" },
    { id: "acc_org_mhec", email: "board@example.com", password: "preview", emailVerified: true, displayName: "MHEC board", roles: ["family", "organization"], approvedReviewCount: 0, createdAt: "2026-11-10T15:00:00Z" },
    { id: "acc_david", email: "david@example.com", password: "preview", emailVerified: true, displayName: "David", roles: ["admin", "family"], approvedReviewCount: 0, createdAt: "2026-11-01T12:00:00Z" }
  ],
  reviews: [
    { id: "rev_published", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", authorId: "acc_family_chen", status: "published", ratings: { welcoming: 5, organized: 4, communication: 4 }, body: "Easy to join mid-year. The weekly plan was posted in advance and the campus day ran on time.", holdReasons: [], flagCount: 1, counted: true, createdAt: "2026-11-12T15:00:00Z", publishedAt: "2026-11-12T15:00:00Z" },
    { id: "rev_held_new_account", listingId: "spark-joy-homeschool-co-operative-jackson", authorId: "acc_family_new", status: "held", ratings: { welcoming: 2, organized: 3 }, body: "The forest day was fine, but the meeting place changed twice and we were not told until that morning.", holdReasons: ["new-account"], flagCount: 0, counted: false, createdAt: "2026-11-22T18:30:00Z", publishedAt: null },
    { id: "rev_held_filter", listingId: "bellevue-tutorial-cordova", authorId: "acc_family_chen", status: "held", ratings: { communication: 2 }, body: "Call Jamie Cole at 555-0148 if you want the same tutor we used.", holdReasons: ["phone", "possible-name"], flagCount: 0, counted: true, createdAt: "2026-11-20T15:00:00Z", publishedAt: null }
  ],
  replies: [
    { id: "reply_mhec", reviewId: "rev_published", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", authorId: "acc_org_mhec", status: "published", body: "Thank you. The semester calendar is on our website, and new families can visit one Thursday before joining.", createdAt: "2026-11-13T15:00:00Z" }
  ],
  flags: [
    { id: "flag_1", targetType: "review", targetId: "rev_published", authorId: "acc_family_new", reason: "This describes a different campus than the one we attend.", createdAt: "2026-11-21T15:00:00Z" }
  ],
  claims: [
    { id: "claim_mhec", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_org_mhec", status: "Verified", method: "manual", verifiedAt: "2026-11-10T16:00:00Z", codePlain: "" }
  ],
  overrides: [
    { id: "memphis-homeschool-enrichment-cooperative-mhec-memphis", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", openSpots: "A few Thursday spots left", meetingDays: "Thursdays", costNotes: "Membership required; contact for fees.", description: "", website: "", email: "", phone: "", lastUpdated: "2026-11-18", updatedBy: "acc_org_mhec", pending: null }
  ],
  portals: [
    { id: "memphis-homeschool-enrichment-cooperative-mhec-memphis", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", active: true, source: "admin-grant", grantedBy: "acc_david", startedAt: "2026-11-18T15:00:00Z", publicBadge: false }
  ],
  members: [
    { id: "memphis-homeschool-enrichment-cooperative-mhec-memphis:acc_org_mhec", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_org_mhec", role: "organizer", status: "active" },
    { id: "memphis-homeschool-enrichment-cooperative-mhec-memphis:acc_family_chen", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_chen", role: "member", status: "active" },
    { id: "memphis-homeschool-enrichment-cooperative-mhec-memphis:acc_family_new", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_new", role: "member", status: "active" }
  ],
  invites: [],
  children: [
    { id: "child_1", accountId: "acc_family_chen", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", firstName: "Sam", grade: "4", private: true }
  ],
  offerings: [
    { id: "off_art", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", kind: "class", title: "Thursday art", capacity: 1, feeCents: 2000, startsOn: "2027-01-08", endsOn: "2027-05-14" }
  ],
  enrollments: [
    { id: "enr_1", offeringId: "off_art", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_chen", childId: "child_1", state: "enrolled", waitlistPosition: null, paymentState: "due", createdAt: "2026-11-19T15:00:00Z" },
    { id: "enr_2", offeringId: "off_art", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_new", childId: "", state: "waitlist", waitlistPosition: 1, paymentState: "not-required", createdAt: "2026-11-19T16:00:00Z" }
  ],
  payments: [
    { id: "due_spring", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_chen", kind: "dues", label: "Spring dues (test)", amountCents: 4000, paymentState: "paid-test", method: "mark-as-paid", platformShareCents: null, summary: "Test record: $40.00 dues, platform share not set, not collected.", collected: false, createdAt: "2026-11-19T15:00:00Z" },
    { id: "pay_art", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", accountId: "acc_family_chen", kind: "class-fee", label: "Thursday art", amountCents: 2000, enrollmentId: "enr_1", offeringId: "off_art", paymentState: "due", method: "", platformShareCents: null, summary: "", collected: false, createdAt: "2026-11-19T15:00:00Z" }
  ],
  announcements: [
    { id: "ann_1", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", title: "Thursday plan", body: "Art meets in the same room. Bring a smock.", audience: "all", status: "outbox", holdReasons: [], authorId: "acc_org_mhec", createdAt: "2026-11-20T15:00:00Z" }
  ],
  deliveries: [
    { id: "ann_1:acc_family_chen", announcementId: "ann_1", accountId: "acc_family_chen", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis" },
    { id: "ann_1:acc_family_new", announcementId: "ann_1", accountId: "acc_family_new", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis" },
    { id: "ann_1:acc_org_mhec", announcementId: "ann_1", accountId: "acc_org_mhec", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis" }
  ],
  rotation: [
    { id: "rot_1", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", date: "2027-01-08", role: "Teach", accountId: "acc_family_chen" }
  ],
  looking: [
    { id: "need_spanish", authorId: "acc_family_chen", title: "Spanish tutor near Collierville", body: "Looking for a weekly Spanish class or tutor for elementary ages, in person, near Collierville.", category: "tutors", state: "TN", county: "Shelby", city: "Collierville", status: "published", holdReasons: [], flagCount: 0, createdAt: "2026-11-20T15:00:00Z", expiresAt: "2027-02-20T15:00:00Z" }
  ],
  lookingReplies: [],
  events: [
    { id: "evt_park", authorId: "acc_family_chen", listingId: "memphis-homeschool-enrichment-cooperative-mhec-memphis", title: "Park day at Shelby Farms", summary: "Informal meet-up by the visitor center. No signup.", startsAt: "2026-12-03T16:00:00Z", endsAt: "2026-12-03T18:00:00Z", state: "TN", county: "Shelby", city: "Memphis", venue: "Shelby Farms visitor center", status: "published", holdReasons: [], flagCount: 0, createdAt: "2026-11-18T15:00:00Z" }
  ],
  favorites: [
    { id: "acc_family_chen:spark-joy-homeschool-co-operative-jackson", accountId: "acc_family_chen", listingId: "spark-joy-homeschool-co-operative-jackson", savedAt: "2026-11-15T15:00:00Z", alertOnOpenSpots: true, seenOpenSpots: null }
  ],
  history: []
};
