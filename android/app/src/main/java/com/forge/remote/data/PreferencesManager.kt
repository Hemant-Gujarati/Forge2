package com.forge.remote.data

import android.content.Context
import android.content.SharedPreferences

class PreferencesManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("forge_remote_prefs", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString("server_url", "http://10.0.2.2:5000") ?: "http://10.0.2.2:5000"
        set(value) = prefs.edit().putString("server_url", value.trimEnd('/')).apply()

    var authToken: String
        get() = prefs.getString("auth_token", "") ?: ""
        set(value) = prefs.edit().putString("auth_token", value).apply()

    val isPaired: Boolean
        get() = authToken.isNotEmpty()

    fun clear() {
        prefs.edit().clear().apply()
    }
}
