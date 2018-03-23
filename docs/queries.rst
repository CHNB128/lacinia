Queries
=======

.. sidebar:: GraphQL Spec

   Read about :spec:`operations <Executing-Operations>`.

Queries are responsible for generating the initial resolved values that will be
picked apart to form the result map.

Other than that, queries are just the same as any other field.
Queries have a type, and accept arguments.

Queries are defined using the ``:queries`` key of the schema.

.. literalinclude:: _examples/query-def.edn
   :language: clojure

Queries may also be defined as fields of the :doc:`root query object <roots>`.

The :doc:`field resolver <resolve/index>` for a query is passed nil
as the the value (the third parameter).
Outside of this, the query field resolver is the same as any field resolver
anywhere else.

In the GraphQL specification, it is noted that queries are idempotent; if
the query document includes multiple queries, they are allowed to execute
in :doc:`parallel <resolve/async>`.
