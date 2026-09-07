// A .h header (not .hpp), the case a real project hits: a header carrying
// oneline need markers that never appears in compile_commands.json (headers are
// not compiled translation units). libclang infers the C language from the .h
// extension, so parsing it with a C++ -std flag would return a NULL translation
// unit. The engine pins -x to the -std for standalone parses, so this header is
// parsed as C++ and its markers are extracted (not dropped, not crashing).

// @Plain Header, IMPL_HDR_PLAIN, impl, [REQ_HDR]
void plain_header_fn();
