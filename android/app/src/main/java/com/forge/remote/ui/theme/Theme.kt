package com.forge.remote.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val CyanPrimary = Color(0xFF00E5FF)
val CyanSecondary = Color(0xFF00B0FF)
val DarkBackground = Color(0xFF121212)
val DarkSurface = Color(0xFF1E1E1E)
val SurfaceVariant = Color(0xFF2C2C2C)
val OnDark = Color(0xFFE0E0E0)
val ApprovedGreen = Color(0xFF00E676)
val RejectedRed = Color(0xFFFF5252)

private val DarkColorScheme = darkColorScheme(
    primary = CyanPrimary,
    secondary = CyanSecondary,
    background = DarkBackground,
    surface = DarkSurface,
    surfaceVariant = SurfaceVariant,
    onPrimary = Color.Black,
    onBackground = OnDark,
    onSurface = OnDark,
)

@Composable
fun ForgeRemoteTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
