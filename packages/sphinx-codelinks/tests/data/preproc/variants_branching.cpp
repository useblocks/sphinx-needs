// @Always Present, IMPL_ALWAYS, impl, [REQ_BASE]
void always() {}

#ifdef VARIANT_A
// @Variant A Feature, IMPL_VAR_A, impl, [REQ_FEAT_A]
void variant_a() {}
#else
// @Variant B Feature, IMPL_VAR_B, impl, [REQ_FEAT_B]
void variant_b() {}
#endif

#if PROTOCOL_VERSION >= 3
// @Protocol V3, IMPL_PROTO_3, impl, [REQ_PROTO]
void proto_v3() {}
#endif

#if defined(PLATFORM_LINUX) && defined(VARIANT_A)
// @Linux And A, IMPL_LINUX_A, impl, [REQ_COMBO]
void linux_and_a() {}
#endif
