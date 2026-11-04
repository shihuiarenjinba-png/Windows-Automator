# runFullTrust — Submission Options automation

## Where the explanation is used

The Packages page only detects the restricted capability and shows the package acceptance warning.

The explanation belongs in:

`Submission Options -> Restricted capabilities -> runFullTrust`

Microsoft requires the submission to explain why each restricted capability is needed and how it is used.

## Automation policy

1. Read the actual MSIX manifest.
2. Detect restricted capabilities from package evidence.
3. For `runFullTrust`, generate the approved internal template.
4. Unknown restricted capabilities are never invented; they become HOLD.
5. The explanation must be written only to the exact observed `runFullTrust` field in Submission Options.
6. Save Submission Options.
7. Reload and verify the same explanation remains.
8. Keep `Submit for certification` and `Publish` outside the automation.

## runFullTrust template

For a game:

> This product is a packaged Windows desktop game. The runFullTrust capability is required because the package launches its normal desktop process at the standard desktop (medium integrity) trust level rather than as an AppContainer application. The capability is used only to run the packaged desktop game and provide its normal local desktop functionality. It is not used to request administrator elevation.

For an app, `game` is replaced with `application`.

The script does not claim administrator rights, unrestricted system access, or capabilities not proven by the package.

## Current live status

The exact Submission Options selectors for the restricted capability field, Save success, and post-save reload verification have not yet been observed for the MSIX Game route.

Therefore the checked-in selector map contains fail-closed placeholders and the live route remains disabled until those selectors are observed.
