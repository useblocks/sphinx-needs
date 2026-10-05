// @need-ids: REQ_001
void implements_a() {}
// @need-ids: REQ_002, REQ_001
int helper(int a) { return a + 1; }
// @need-ids: NOSUCH_ID
void dangling() {}
// @need-ids: REQ_003
void deep() {}
