# @Module function, IMPL_FN, impl
def handler():
    pass


# @need impl: Decorated
# :id: IMPL_ML
# @endneed
@register  # noqa: F821
def decorated():
    # @need-ids: REQ_001
    pass


class Shape:
    # @Area method, IMPL_METHOD, impl
    def area(self):
        return 0.0


limit = 3  # @Unattached, IMPL_NONE, impl
