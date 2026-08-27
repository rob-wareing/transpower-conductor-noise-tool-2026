# Detection Logic

Every reading is processed twice, by two independent rule sets, and both results
are kept side by side in the database under the columns "Original" and
"Updated 2026".

Use the "Detection logic" dropdown on the Charts and Trends tabs to switch
between the two - they will generally show different numbers of qualifying
readings and slightly different levels for the same site and date range, since
they're not filtering the same way.

| Criteria | Original | Updated 2026 |
| --- | --- | --- |
| Time | 22:00-07:00 | 22:00-05:00 |
| Rain | Wet if this or the previous reading had rain > 0 | Wet if this reading's rain >= 0.05 mm (previous reading no longer counted) |
| Wind | Wind speed <= 2.0 m/s | Wind speed < 1.5 m/s |
| Leq-L90 | Excluded if (Leq - L90) > 2.0 dB | No Leq-L90 check (removed) |
| RMSE of Leq | Not checked | Excluded if RMSE of the 1-second Leq trace > 0.75 (rows with no RMSE data still pass) |
| Line status | Not checked | Live |
| Rain and wind measurement | No explicit check (a missing reading fails the Wind/Rain checks above by comparison) | Row dropped outright if either wind speed or rain is missing |

