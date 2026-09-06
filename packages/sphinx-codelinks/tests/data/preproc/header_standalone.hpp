#ifndef HEADER_STANDALONE_HPP
#define HEADER_STANDALONE_HPP

// @Header Always, IMPL_HDR_ALWAYS, impl, [REQ_HDR]
void hdr_always();

#ifdef VARIANT_A
// @Header Variant A, IMPL_HDR_VAR_A, impl, [REQ_HDR_A]
void hdr_variant_a();
#endif

#endif  // HEADER_STANDALONE_HPP
