#include <stdbool.h>

/**
 * @need impl: Lock an account after repeated failures
 * :id: IMPL_RATE_LIMIT_1
 * :links: FE_MULTILINE_NEEDS
 *
 * After **five** failed attempts the account is locked, as
 * :need:`FE_MULTILINE_NEEDS` lets a source comment say:
 *
 * - the count is kept in ``failed_attempts``;
 * - a successful login resets it.
 * @endneed
 */
bool login(const char *user, const char *password) {
    return false;
}
