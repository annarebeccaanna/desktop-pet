"""KI-Chat: Anbieter, Schlüssel und Gesprächslogik (ohne Qt, testbar).

* ``providers/`` – je Anbieter eine kleine Datei; ein neuer Anbieter ist eine neue Datei.
* ``detect``     – Anbieter am Präfix des Keys erkennen (lokal, ohne Netzwerk).
* ``keys``       – API-Keys im Windows-Anmeldeinformationsspeicher (nie in der JSON, nie im Log).
* ``chat``       – Gesprächsverlauf und Persönlichkeit des Tiers.
"""
