TEST DOCUMENT NEEDUML OPTION WARNINGS
=====================================

.. needuml::
   :config: mixing,no_such_config
   :extra: url:https://example.com/a:b, plain:value ,broken

   card "{{url}}" as a
   card "{{plain}}" as b
   a -> b

.. needuml::
   :scale: not-a-number

   card "fallback scale" as c
