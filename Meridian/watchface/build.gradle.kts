plugins {
    alias(libs.plugins.android.application)
}

// Release signing is read from Gradle properties, never from this repository.
// Put the four keys in ~/.gradle/gradle.properties; `make signing-help` prints
// them. When any of them is absent the release build falls back to the debug
// key so a clone still builds, and warns loudly that the artifact is not
// publishable.
val relStoreFile: String?     = providers.gradleProperty("watch8.storeFile").orNull
val relStorePassword: String? = providers.gradleProperty("watch8.storePassword").orNull
val relKeyAlias: String?      = providers.gradleProperty("watch8.keyAlias").orNull
val relKeyPassword: String?   = providers.gradleProperty("watch8.keyPassword").orNull

val hasReleaseSigning: Boolean =
    listOf(relStoreFile, relStorePassword, relKeyAlias, relKeyPassword)
        .all { !it.isNullOrBlank() }

android {
    // Watch Face Format packages are resource-only: no Java/Kotlin sources.
    enableKotlin = false
    namespace = "com.watch8.meridian"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.watch8.meridian"
        // WFF v2 requires Wear OS 5 / API 34. Matches the Complications/Weather/Flavors v2 samples.
        minSdk = 34
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(relStoreFile!!)
                storePassword = relStorePassword
                keyAlias = relKeyAlias
                keyPassword = relKeyPassword
                // Play requires v2 at minimum; v1 keeps older tooling happy.
                enableV1Signing = true
                enableV2Signing = true
            }
        }
    }

    buildTypes {
        // The official samples set isMinifyEnabled = true on both build types,
        // but this package has hasCode="false" and no sources, so R8 has no
        // classes to process. Leaving it on only adds a minify task and makes
        // AGP warn that debug is both debuggable and minified.
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = false
            // Must stay false, otherwise watch face resources can be stripped.
            // (AGP also requires minify for shrinking, so this is belt and braces.)
            isShrinkResources = false

            signingConfig =
                if (hasReleaseSigning) signingConfigs.getByName("release")
                else signingConfigs.getByName("debug")
        }
    }
}

gradle.taskGraph.whenReady {
    if (!hasReleaseSigning && allTasks.any { it.name.contains("Release") }) {
        logger.warn(
            "\n*** watch8: release signing is NOT configured. Building with the debug key.\n" +
            "*** This artifact cannot be uploaded to Play. Run `make signing-help`.\n"
        )
    }
}
